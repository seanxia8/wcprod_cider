#!/usr/bin/python
import sys,os
import shutil
import subprocess
from wcprod import wcprod_project,wcprod_db
import numpy as np
import yaml
import time

TEMPLATE_WCSIM_RUN='''#!/bin/bash
cd %s
./scripts/run.sh %s ./build/macros/tuning_parameters.mac
'''
TEMPLATE_CONVERT_RUN='''#!/bin/bash
source /src/scripts/sourceme.sh
python3 ${DATATOOLS}/convert.py ./convert.yaml
'''

TEMPLATE_REBIN_RUN='''#!/bin/bash
source /src/scripts/sourceme.sh
python3 ${DATATOOLS}/rebin.py ./rebin.yaml ./uniform_check.yaml
'''

WRAPUP_CONFIG_FILE_NAME='wrapup_job.yaml'

TEMPLATE_G4='''/run/verbose                           1
/tracking/verbose                      0
/Tracking/trackParticle                0
/hits/verbose                          0
/random/setSeeds                       0 0
/WCSim/random/seed                     0
/WCSim/WCgeom                          nuPRISMBeamTest_16cShort_mPMT
/WCSim/PMT/ReplicaPlacement            false
/WCSim/Geometry/RotateBarrelHalfTower  true
/WCSim/PMT/PositionVariation           0 mm
/WCSim/PMT/PositionFile                data/mPMT_Position_WCTE.txt
/WCSim/mPMT/PMTtype_inner              PMT3inchR14374_WCTE
/WCSim/Construct
/WCSim/PMTQEMethod                     DoNotApplyQE
/WCSim/PMTCollEff                      off
/WCSim/SavePi0                         false
/DAQ/Digitizer                         SKI
/DAQ/Trigger                           NoTrigger
/control/execute                       macros/daq.mac
/DarkRate/SetDetectorElement           tank
/DarkRate/SetDarkRate                  0 kHz
/DarkRate/SetDarkMode                  1
/DarkRate/SetDarkHigh                  100000
/DarkRate/SetDarkLow                   0
/DarkRate/SetDarkWindow                4000
/mygen/generator                       voxel
/mygen/r0_Vox                          %f mm
/mygen/r1_Vox                          %f mm
/mygen/z0_Vox                          %f mm
/mygen/z1_Vox                          %f mm
/mygen/phi0_Vox                        %f
/mygen/phi1_Vox                        %f
/Tracking/fractionOpticalPhotonsToDraw 0
/WCSimIO/RootFile                      %s
/WCSimIO/SaveRooTracker                0
/run/beamOn                            %d
'''

TEMPLATE_CHECK_SHELL='''#!/bin/bash

source %s
%s/build/app/check_uniform_voxel -f %s -c %s/%s.yaml -q
'''

TEMPLATE_CHECK_CMACRO='''r0: %f
r1: %f
phi0: %f
phi1: %f
z0: %f
z1: %f
criterion: -0.1
wrapup_file: %s
'''

TEMPLATE_CONVERT='''# WCSim config file for ROOT->HDF5 conversion

data:
  file_name: %s
  output_file: %s
  n_photons: %d
  nevents_per_file: %d
  root_branches:
      event_info:
        - [pid, np.int32, 1]
        - [position, np.float32, 3]
        - [direction, np.float32, 3]
        - [energy, np.float32, 1]
      digi_hits:
        - [pmt, np.int32, 10184] # pmt id
        - [charge, np.float32, 10184]
        - [time, np.float32, 10184]
        - [trigger, np.int32, 10184] # pmt trigger id

detector:
  npmts: 10184

format:
  compression: gzip
  compression_opt: 5
'''

TEMPLATE_REBIN='''# binning scheme for photon position and direction

Data:
  input_file: %s
  output_file: %s
  dset_names:
      - position
      - direction
      - digi_pmt
      - digi_charge
      - digi_time

Position:
  rmax: %f
  zmax: %f
  gap_space: %f
  n_bins_phi0: %f

Direction:
  gap_angle: %f

Energy:
  n_bins: 1

Action:
  wall_cut: True
  towall_cut: True

Database:
  db_file: %s
  num_shards: %d

Detector:
  npmt: 10184

Format:
  compression: gzip
  compression_opt: 5
  drop_unhit: True
'''

ERROR_MISSING_ARG_COUNT=1
ERROR_MISSING_CONFIGFILE=2
ERROR_MISSING_KEYWORD=3
ERROR_MISSING_DBFILE=4
ERROR_PROJECT_NOT_FOUND=5
ERROR_STORAGE_CREATION=6

def parse_config(cfg_file):

	if not os.path.isfile(cfg_file):
		print(f"ERROR: configuration file '{cfg_file}' does not exist.")
		sys.exit(ERROR_MISSING_CONFIGFILE)

	with open(cfg_file,'r') as f:
		cfg=yaml.safe_load(f)

		for key in ['DBFile','Project','NPhotons','NEvents','Storage','ROOT_SETUP', 'WCSIM_HOME', 'WCSIM_ENV',
					'Rebin_DBfile', 'WC_rmax', 'WC_zmax',
					'Rebin_gap_space', 'Rebin_gap_angle', 'Rebin_n_bins_phi0', 'Num_shards']:
			if not key in cfg.keys():
				print('ERROR: configuration lacking a keyword:',key)
				sys.exit(ERROR_MISSING_KEYWORD)

		if not os.path.isfile(cfg['DBFile']):
			print(f"ERROR: DBFile '{cfg['DBFile']}' does not exist.")
			sys.exit(ERROR_MISSING_DBFILE)

		return cfg

def main():

	# Step 0: parse job configurations
	if not len(sys.argv)==2:
		print(f'ERROR: needs exactly 2 arguments ({len(sys.argv)} given) ')
		sys.exit(ERROR_INVALID_ARG_COUNT)

	cfg = parse_config(sys.argv[1])

	dbfile   = cfg['DBFile']
	project  = cfg['Project']
	nphotons = int(cfg['NPhotons'])
	nevents  = int(cfg['NEvents'])
	storage_root = cfg['Storage']
	root_setup   = cfg['ROOT_SETUP']
	wcsim_home   = cfg['WCSIM_HOME']
	wcsim_env    = cfg['WCSIM_ENV']
	rebin_dbfile = cfg['Rebin_DBfile']
	rmax = cfg['WC_rmax']
	zmax = cfg['WC_zmax']
	rebin_gap_space = cfg['Rebin_gap_space']
	rebin_gap_angle = cfg['Rebin_gap_angle']
	rebin_n_bins_phi0 = cfg['Rebin_n_bins_phi0']
	num_shards = cfg['Num_shards']

	db=wcprod_db(dbfile)
	if not db.exist_project(project):
		print(f"ERROR: project '{project}' not found in the database {dbfile}.")
		sys.exit(ERROR_PROJECT_NOT_FOUND)

	cfg = db.get_random_config(project, prioritize=True, size=1000)
	file_ctr = cfg['file_ctr']
	config_id = cfg['config_id']
	r0 = cfg['r0']
	r1 = cfg['r1']
	z0 = cfg['z0']
	z1 = cfg['z1']
	phi0 = cfg['phi0']
	phi1 = cfg['phi1']

	# Step 1: prepare/verify the storage space
	unit_K=100
	unit_M=unit_K*1000
	tier1 = int(config_id / unit_M)
	tier2 = int((config_id - unit_M*tier1) / unit_K)
	storage_path = 'tier1_%03d/tier2_%03d/tier3_%09d' % (tier1,tier2,config_id)
	storage_path = os.path.join(storage_root,storage_path)

	try:
		os.makedirs(storage_path,exist_ok=True)
	except OSError:
		print(f"Failed to create the storage directory '{storage_path}'")
		sys.exit(ERROR_STORAGE_CREATION)

	os.chdir(storage_path)

	# Step 2: prepare G4 macro
	out_file   = '%s/out_%s_%09d_%03d.root' % (storage_path,project,config_id,file_ctr)
	contents = TEMPLATE_G4 % (r0,r1,z0,z1,phi0,phi1,out_file,nevents)
	with open(f'{storage_path}/log.txt','a') as f:
		f.write('\n\n'+contents+'\n\n')
	with open(f'{storage_path}/g4.mac','w') as f:
		f.write(contents)

	# Step 3: store the configuration for the wrapup file
	wrapup_cfg = dict(DBFile=dbfile,Project=project,ConfigID=config_id,
		StartTime=time.time(),
		Destination=storage_path,Output=out_file,
		NPhotons=nphotons,NEvents=nevents)
	wrapup_file = WRAPUP_CONFIG_FILE_NAME
	#wrapup_record = '%s/wrapup_%s_%09d_%03d.yaml' % (storage_path, project,config_id,file_ctr)
	with open(f'{storage_path}/{wrapup_file}', 'a') as f:
	    yaml.dump(wrapup_cfg, f, default_flow_style=False)
	#with open(wrapup_record, 'w') as f:
    #		yaml.dump(wrapup_cfg, f, default_flow_style=False)
	with open(f'{storage_path}/log.txt','a') as f:
		f.write('\n\n')
		yaml.dump(wrapup_cfg, f, default_flow_style=False)

	# Step 4: prepare the check script for wcsim file
	cmacro_name = 'uniform_check'
	contents = TEMPLATE_CHECK_CMACRO % (r0,r1,phi0,phi1,z0,z1,f'{storage_path}/{wrapup_file}')
	with open(f'{storage_path}/log.txt','a') as f:
		f.write('\n\n'+contents+'\n\n')
	with open('%s/%s.yaml' % (storage_path, cmacro_name),'w') as f:
		f.write(contents)

	contents = TEMPLATE_CHECK_SHELL % (wcsim_env, wcsim_home, out_file, storage_path, cmacro_name)
	with open(f'{storage_path}/wcprod_check.sh','w') as f:
		f.write(contents)

	script_wcsim = TEMPLATE_WCSIM_RUN % (wcsim_home, f"{storage_path}/g4.mac")
	with open(f'{storage_path}/run_wcsim.sh', 'w') as f:
		f.write(script_wcsim)

	out_raw_h5 = '%s/raw_%s_%09d_%03d.h5' % (storage_path,project,config_id,file_ctr)
	script_convert = TEMPLATE_CONVERT % (out_file, out_raw_h5, nphotons, nevents)
	with open(f'{storage_path}/convert.yaml', 'w') as f:
		f.write(script_convert)

	out_rebin_h5 = '%s/rebin_%s_%09d_%03d.h5' % (storage_path,project,config_id,file_ctr)
	script_rebin = TEMPLATE_REBIN % (out_raw_h5, out_rebin_h5, rmax, zmax, rebin_gap_space, rebin_n_bins_phi0, rebin_gap_angle, rebin_dbfile, num_shards)
	with open(f'{storage_path}/rebin.yaml', 'w') as f:
		f.write(script_rebin)

	with open(f'{storage_path}/run_convert.sh', 'w') as f:
		f.write(TEMPLATE_CONVERT_RUN)

	with open(f'{storage_path}/run_rebin.sh', 'w') as f:
		f.write(TEMPLATE_REBIN_RUN)

	#sys.exit(0)
	return storage_path

if __name__ == '__main__':
	print(main())
