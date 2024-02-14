#!/usr/bin/python3

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
ERROR_MISSING_EVENT=6
ERROR_PROJECT_NOT_FOUND=7
ERROR_OUTPUT_NOT_PRESENT=8
ERROR_STORAGE_ALREADY_PRESENT=9

def parse_config(cfg_file):

	if not os.path.isfile(cfg_file):
		print(f"ERROR: configuration file '{cfg_file}' does not exist.")
		sys.exit(ERROR_MISSING_CONFIGFILE)

	cfg=yaml.safe_load(cfg_file)

	for key in ['DBFile','ConfigID','Destination','Output','NPhotons','NEvents','NEventsOutput']:
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
	storage  = cfg['Storage']
	out_file = cfg['Output']
	nevents_expected = int(cfg['NEvents'])
	nevents_recorded = int(cfg['NEventsOutput'])

	if not nevents_expected == nevents_recorded:
		print(f"ERROR: the number of events expected ({nevents_expected}) != recorded in file ({nevents_recorded})")
		sys.exit(ERROR_MISSING_EVENT)

	db=wcprod_db(dbfile)
	if not db.exist_project(project):
		print(f"ERROR: project '{project}' not found in the database {dbfile}.")
		sys.exit(ERROR_PROJECT_NOT_FOUND)

	# Step 1: check the output file
	if not os.path.isfile(out_file):
		print(f"ERROR: output file '{out_file}' does not exist.")
		sys.exit(ERROR_OUTPUT_NOT_PRESENT)

	# Step 2: copy to the storage
	storage_file = os.path.join(storage,out_file)
	if os.path.isfile(storage_file):
		print(f"ERROR: output file '{out_file}' already is present in the storage!")
		print(f"  {storage_file}")
		sys.exit(ERROR_STORAGE_ALREADY_PRESENT)

	shutil.copy2(out_file,storage_file)

	# Step 3: check the file in the storage
	if not os.path.isfile(storage_file):
		print(f"ERROR: storage file {storage_file} does not exist.")
		sys.exit(ERROR_STORAGE_NOT_PRESENT)

	# Step 4: log to the database
	db.register_file(project,config_id,storage_file,nphotons)

	sys.exit(0)

if __name__ == '__main__':
	main()


