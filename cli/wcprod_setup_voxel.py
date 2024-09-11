#!/usr/bin/python
import sys,os
import shutil
import subprocess
from wcprod import wcprod_project,wcprod_db
import numpy as np
import yaml
import time

TEMPLATE_WCSIM_RUN='''
#!/bin/bash
cd %s
./scripts/run.sh %s ./build/macros/tuning_parameters.mac
'''

WRAPUP_CONFIG_FILE_NAME='wrapup_job.yaml'

TEMPLATE_G4='''
/run/verbose                           1
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

TEMPLATE_CHECK_SHELL='''
#!/bin/bash

source %s
%s/build/app/check_uniform_voxel -f %s -c %s/%s -q'
'''

TEMPLATE_CHECK_CMACRO='''
r0: %f
r1: %f
phi0: %f
phi1: %f
z0: %f
z1: %f
criterion: -0.1
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

		for key in ['DBFile','Project','NPhotons','NEvents','Storage','ROOT_SETUP', 'WCSIM_HOME', 'WCSIM_ENV']:
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
	wcsim_env    = cfg['WCSI_ENV']

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
	wrapup_record = '%s/wrapup_%s_%09d_%03d.yaml' % (storage_path, project,config_id,file_ctr)
	with open(wrapup_file, 'w') as f:
	    yaml.dump(wrapup_cfg, f, default_flow_style=False)
	with open(wrapup_record, 'w') as f:
		yaml.dump(wrapup_cfg, f, default_flow_style=False)
	with open(f'{storage_path}/log.txt','a') as f:
		f.write('\n\n')
		yaml.dump(wrapup_cfg, f, default_flow_style=False)

	# Step 4: prepare the check script for wcsim file
	cmacro_name = 'uniform_check'
	contents = TEMPLATE_CHECK_CMACRO % (r0,r1,phi0,phi1,z0,z1)
	with open(f'{storage_path}/log.txt','a') as f:
		f.write('\n\n'+contents+'\n\n')
	with open('%s/%s.yaml' % (storage_path, cmacro_name),'w') as f:
		f.write(contents)

	contents = TEMPLATE_CHECK_SHELL % (wcsim_env, storage_path, out_file, storage_path, cmacro_name)
	with open(f'{storage_path}/wcprod_check.sh','w') as f:
		f.write(contents)

	script_wcsim = TEMPLATE_WCSIM_RUN % (wcsim_home, f"{storage_path}/g4.mac")
	with open(f'{storage_path}/run_wcsim.sh', 'w') as f:
		f.write(script_wcsim)

	sys.exit(0)

if __name__ == '__main__':
	main()
