#!/usr/bin/python
import sys,os
import shutil
import subprocess
from wcprod import wcprod_project,wcprod_db
import numpy as np
import yaml

WRAPUP_CONFIG_FILE_NAME='wrapup_job.yaml'

TEMPLATE_G4='''
/run/verbose                           1
/tracking/verbose                      0
/Tracking/trackParticle                0
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
/control/execute                       %s/macros/daq.mac
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
/Tracking/fractionOpticalPhotonsToDraw 100
/WCSimIO/RootFile                      %s
/WCSimIO/SaveRooTracker                0
/run/beamOn                            %d
'''

TEMPLATE_CHECK_SHELL='''#!/bin/bash
#!/bin/bash

source %s
root -l -b -q '%s.C()'
'''

TEMPLATE_CHECK_CMACRO='''
#include <iostream>
#include <stdio.h>     
#include <stdlib.h>
#include <string>
#include <fstream>
// Simple example of reading a generated Root file
void %s()
{
	gSystem->Load("${WCSIMDIR}/build/libWCSimRoot.so");

	TFile *file;
	file = new TFile("%s","read");
	if (!file->IsOpen()){
	  cout << "Error, could not open input file: " << input_file << endl;
	  return -1;
	}
  
	TTree *tree = (TTree*)file->Get("wcsimT");
  
	int nevent = tree->GetEntries();

	ofstream fout;
	fout.open("%s",std::ios_base::app);
	fout << std::endl << "NEventsOutput: " << nevent << std::endl;
	fout.close();

	fout.open("%s",std::ios_base::app);
	fout << std::endl << "NEventsOutput: " << nevent << std::endl;
	fout.close();
}
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

		for key in ['DBFile','Project','NPhotons','NEvents','Storage','WCSIM_BUILDDIR','ROOT_SETUP']:
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
	wcsim_dir    = cfg['WCSIM_BUILDDIR']

	db=wcprod_db(dbfile)
	if not db.exist_project(project):
		print(f"ERROR: project '{project}' not found in the database {dbfile}.")
		sys.exit(ERROR_PROJECT_NOT_FOUND)

	# Step 1: prepare G4 macro
	cfg=db.get_random_config(project,prioritize=True,size=1000)
	config_id = cfg['config_id']
	file_ctr  = cfg['file_ctr' ]
	dz = np.cos(cfg['theta']/180.*np.pi)
	dx = np.sin(cfg['theta']/180.*np.pi)*np.cos(cfg['phi']/360.*2*np.pi)
	dy = np.sin(cfg['theta']/180.*np.pi)*np.sin(cfg['phi']/360.*2*np.pi)
	out_file   = 'out_%s_%09d_%03d.root' % (project,config_id,file_ctr)

	contents = TEMPLATE_G4 % (wcsim_dir,dx,dy,dz,cfg['x'],cfg['y'],cfg['z'],nphotons,out_file,nevents)
	with open('log.txt','a') as f:	
		f.write('\n\n'+contents+'\n\n')
	with open('g4.mac','w') as f:
		f.write(contents)

	# Step 2: prepare/verify the storage space
	unit_K=1000
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

	# Step 3: store the configuration for the wrapup file
	wrapup_cfg = dict(DBFile=dbfile,Project=project,ConfigID=config_id,Destination=storage_path,Output=out_file,NPhotons=nphotons,NEvents=nevents)
	wrapup_file = WRAPUP_CONFIG_FILE_NAME
	wrapup_record = 'wrapup_%s_%09d_%03d.yaml' % (project,config_id,file_ctr)
	with open(wrapup_file, 'w') as f:
	    yaml.dump(wrapup_cfg, f, default_flow_style=False)
	with open(wrapup_record, 'w') as f:
		yaml.dump(wrapup_cfg, f, default_flow_style=False)
	with open('log.txt','a') as f:
		f.write('\n\n')
		yaml.dump(wrapup_cfg, f, default_flow_style=False)

	# Step 4: prepare the check script for wcsim file
	cmacro_name = 'wcprod_check'
	contents = TEMPLATE_CHECK_CMACRO % (cmacro_name,out_file,wrapup_file,wrapup_record)
	with open('log.txt','a') as f:
		f.write('\n\n'+contents+'\n\n')
	with open('%s.C' % cmacro_name,'w') as f:
		f.write(contents)

	contents = TEMPLATE_CHECK_SHELL % (root_setup,cmacro_name)
	with open('wcprod_check.sh','w') as f:
		f.write(contents)

	sys.exit(0)

if __name__ == '__main__':
	main()
