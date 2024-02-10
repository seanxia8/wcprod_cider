#!/usr/bin/python3
g4_template='''
/run/verbose                           1
/tracking/verbose                      0
/hits/verbose                          0
/random/setSeeds                       0 0
/WCSim/random/seed                     0
/WCSim/WCgeom                          nuPRISMShort_mPMT
/WCSim/Construct
/WCSim/PMTQEMethod                     DoNotApplyQE
/WCSim/PMTCollEff                      off
/WCSim/SavePi0                         false
/DAQ/Digitizer                         SKI
/DAQ/Trigger                           NDigits
/control/execute                       $WCSIM_BUILDDIR/macros/daq.mac
/DarkRate/SetDarkRate                  0 kHz
/DarkRate/SetDarkMode                  1
/DarkRate/SetDarkHigh                  100000
/DarkRate/SetDarkLow                   0
/DarkRate/SetDarkWindow                4000
/mygen/generator                       gps
/gps/particle                          opticalphoton
/gps/energy                            2.505 eV
/gps/direction                         %f %f %f
/gps/position                          %f %f %f cm
/gps/number                            %d
/Tracking/fractionOpticalPhotonsToDraw 0.0
/WCSimIO/RootFile                      %s
/WCSimIO/SaveRooTracker                0
/run/beamOn                            50
'''

import sys,os
import shutil
import subprocess
from wcprod import wcprod_project,wcprod_db
import numpy as np
import yaml

ERROR_MISSING_ARG_COUNT=1
ERROR_MISSING_CONFIGFILE=2
ERROR_MISSING_KEYWORD=3
ERROR_MISSING_DBFILE=4
ERROR_MISSING_WCSIM_BUILDDIR=5
ERROR_PROJECT_NOT_FOUND=6
ERROR_OUTPUT_NOT_PRESENT=7
ERROR_STORAGE_CREATION=8
ERROR_STORAGE_ALREADY_PRESENT=9

def parse_config(cfg_file):

	if not os.path.isfile(cfg_file):
		print(f"ERROR: configuration file '{cfg_file}' does not exist.")
		sys.exit(ERROR_MISSING_CONFIGFILE)

	cfg=yaml.safe_load(cfg_file)

	for key in ['DBFile','Project','NPhotons','Storage','WCSIM_BUILDDIR']:
		if not key in cfg.keys():
			print('ERROR: configuration lacking a keyword:',key)
			sys.exit(ERROR_MISSING_KEYWORD)

	if not os.path.isfile(cfg['DBFile']):
		print(f"ERROR: DBFile '{cfg['DBFile']}' does not exist.")
		sys.exit(ERROR_MISSING_DBFILE)

	if not os.path.isdir(cfg['WCSIM_BUILDDIR']):
		print(f"ERROR: WCSIM_BUILDDIR '{cfg['WCSIM_BUILDDIR']}' is not a directory.")
		sys.exit(ERROR_MISSING_WCSIM_BUILDDIR)

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
	storage_root = cfg['Storage']

	db=wcprod_db(dbfile)
	if not db.exist_project(project):
		print(f"ERROR: project '{project}' not found in the database {dbfile}.")
		sys.exit(ERROR_PROJECT_NOT_FOUND)

	# Step 1: prepare geant4 macro
	cfg=db.get_random_config(project,prioritize=True,size=1000)
	config_id = cfg['config_id']
	file_ctr  = cfg['file_ctr' ]
	dz = np.cos(cfg['theta']/180.*np.pi)
	dx = np.sin(cfg['theta']/180.*np.pi)*np.cos(cfg['phi']/360.*2*np.pi)
	dy = np.sin(cfg['theta']/180.*np.pi)*np.sin(cfg['phi']/360.*2*np.pi)

	macro_file = 'wcprod_%s_%09d.mac'    % (project,config_id)
	log_file   = 'log_%s_%09d.log'       % (project,config_id)
	out_file   = 'out_%s_%09d_%03d.root' % (project,config_id,file_ctr)

	with open(macro_file,'w') as f:
		contents = template % (dx,dy,dz,cfg['x'],cfg['y'],cfg['z'],nphotons,out_file)
		f.write(contents)

	# Step 2: run geant 4
	with open(log_file,'w') as f:
		proc=subprocess.run(['$WCSIM_BUILDDIR/WCSim',macro_file],
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT)
		for line in proc.stdout:
			sys.stdout.write(line)
			f.write(line)
		proc.wait()

	# Step 3: check the output file
	if not os.path.isfile(out_file):
		print(f"ERROR: output file '{out_file}' does not exist.")
		sys.exit(ERROR_OUTPUT_NOT_PRESENT)

	# Step 4: copy to the storage
	unit_K=1000
	unit_M=unit_K*1000
	tier3 = config_id % unit_M
	tier2 = (config_id - unit_M*tier3) % unit_K
	storage_path = 'tier1_%03d/tier2_%03d/tier3_%09d' % (tier3,tier2,config_id)
	storage_path = os.path.join(storage_root,storage_path)

	try:
		os.makedirs(storage_path,exist_ok=True)
	except OSError:
		print(f"Failed to create the storage directory '{storage_path}'")
		sys.exit(ERROR_STORAGE_CREATION)

	storage_file = os.path.join(storage_path,out_file)
	if os.path.isfile(storage_file):
		print(f"ERROR: output file '{out_file}' already is present in the storage!")
		print(f"  {storage_file}")
		sys.exit(ERROR_STORAGE_ALREADY_PRESENT)

	shutil.copy2(out_file,storage_file)

	# Step 5: check the file in the storage
	if not os.path.isfile(storage_file):
		print(f"ERROR: storage file {storage_file} does not exist.")
		sys.exit(ERROR_STORAGE_NOT_PRESENT)

	# Step 5: log to the database
	db.register_file(project,config_id,storage_file,nphotons)

	sys.exit(0)

if __name__ == '__main__':
	main()


