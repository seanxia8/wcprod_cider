#!/usr/bin/python3
import sys,os
import yaml
import wcprod
from datetime import datetime

#for slurm system, e.g. slac, idark
TEMPLATE_slurm='''#!/bin/bash
#SBATCH --job-name=wcprod
#SBATCH --nodes=1
#SBATCH --partition=%s
#SBATCH --account=%s
#SBATCH --output=%s/slurm-%%A-%%a.out
#SBATCH --error=%s/slurm-%%A-%%a.out
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=%d
#SBATCH --mem-per-cpu=%dG
#SBATCH --time=%s                                                                                                
#SBATCH --array=1-%d%%%d
%s
'''

# for condor system, e.g. cern
TEMPLATE_condor = '''notification            = Never
universe                = vanilla
executable              = %s
output                  = %s/$(ClusterId).$(ProcId).out
error                   = %s/$(ClusterId).$(ProcId).error
log                     = %s/$(ClusterId).$(ProcId).log
getenv                  = True
should_transfer_files   = NO
initialdir              = %s
priority                = %d
request_cpus            = %d
request_memory          = %d GB
request_disk            = %d GB
+JobFlavour             = "tomorrow"
+MaxRuntime             = %d
queue %d
'''

TEMPLATE_job_script='''# Set-up a work dir
export WORKDIR=%s
mkdir -p $WORKDIR
cd $WORKDIR

# Generate a configuration file

if [ ! -f setup_job.yaml ]; then
    echo "
    DBFile:   %s
    Project:  %s
    NPhotons: %d
    NSubEvents: %d
    NEvents:  %d
    Storage:  %s
    ROOT_SETUP: /src/root/install/bin/thisroot.sh
    WCSIM_HOME: %s
    WCSIM_ENV: /src/scripts/sourceme.sh
    Cluster: %s
    " > setup_job.yaml
fi

# Execute N times
for (( i=1;i<=%d;i++ ))
do

 echo
 echo "Starting: run counter $i"
 storage_path=$(singularity exec %s %s bash -c "wcprod_setup_voxel.py setup_job.yaml") 2>&1
 
 cd ${storage_path}
 chmod +x ./*

 echo `date` && echo `date` >> log.txt  2>&1
 echo
 echo "Running Geant4"
 echo `date` && echo `date` >> log.txt  2>&1
 singularity exec %s %s ./run_wcsim.sh >> log.txt  2>&1

 echo
 echo "Running check"
 echo `date` && echo `date` >> log.txt  2>&1
 singularity exec %s %s ./wcprod_check.sh >> log.txt  2>&1

 echo
 echo "Wrapping up"
 echo `date` && echo `date` >> log.txt  2>&1
 singularity exec %s %s bash -c "wcprod_wrapup_voxel.py wrapup_job.yaml" >> log.txt  2>&1
 
 echo
 echo "Convert to h5"
 echo `date` && echo `date` >> log.txt  2>&1
 singularity exec %s %s ./run_convert.sh >> log.txt  2>&1 
 
 echo
 echo "Finished!" >> log.txt  2>&1
 echo `date` && echo `date` >> log.txt  2>&1
 echo
done

echo
echo "Exiting" >> log.txt  2>&1
echo `date` >> log.txt  2>&1

cd $WORKDIR
'''

def parse_config(cfg):

    cfg_candidates = wcprod.list_config()

    if not os.path.isfile(cfg) and not cfg in cfg_candidates:
        print(f"Configuration '{cfg}' not found as a file nor keywords.")
        sys.exit(1)

    if os.path.isfile(cfg):
        cfg = yaml.safe_load(open(cfg,'r').read())
    else:
        cfg = yaml.safe_load(open(wcprod.get_config(cfg),'r').read())
    keywords = ['CLUSTER_TYPE','CLUSTER_NAME',
                'WCPROD_STORAGE_ROOT','WCPROD_WORK_DIR','WCPROD_DB_FILE',
                'WCPROD_PROJECT','WCPROD_NEVENTS','WCPROD_NSUBEVENTS','WCPROD_NPHOTONS','WCPROD_NLOOPS',
                'JOB_LOG_DIR','JOB_TIME','JOB_MEM','JOB_DISK_SPACE', 'JOB_PRIORITY',
                'SLURM_ACCOUNT','SLURM_PARTITION','SLURM_PREEMPTABLE','SLURM_NJOBS_CONCURRENT',
                'JOB_NCPU','NJOBS_TOTAL',
                'CONTAINER', 'WCSIM_HOME']

    for key in keywords:
        if not key in cfg.keys():
            print('ERROR: config missing a keyword',key)
            sys.exit(1)

    if not os.path.isfile(cfg['CONTAINER']):
        print(f"ERROR: a container missing '{cfg['CONTAINER']}'")
        sys.exit(1)

    db=wcprod.wcprod_db(cfg['WCPROD_DB_FILE'])
    if not db.exist_project(cfg['WCPROD_PROJECT']):
        print(f"ERROR: project '{cfg['WCPROD_PROJECT']}' not found in the database {cfg['WCPROD_DB_FILE']}.")
        sys.exit(1)

    if 'BIND_PATH' in cfg:
        if not type(cfg['BIND_PATH']) in [type(str()),type(list())]:
            print(f"ERROR: BIND_PATH value '{cfg['BIND_PATH']}' must be a string or a list of strings")
        if type(cfg['BIND_PATH']) == type(str()):
            cfg['BIND_PATH'] = [cfg['BIND_PATH']]

        cmd = '-B '
        for p in cfg['BIND_PATH']:
            if not os.path.isdir(p):
                print(f"ERROR: cannot bind non-existent path '{cfg['BIND_PATH']}' ")
                sys.exit(1)
            cmd = cmd + p + ','

        cfg['BIND_PATH'] = cmd.rstrip(',')
        cfg['BIND_PATH'] = cmd.rstrip(',')
    else:
        cfg['BIND_PATH'] = ''

    return cfg


def main():
    if not len(sys.argv) == 2:
        print('Usage: %s CONFIG' % sys.argv[0])
        sys.exit(1)

    cfg = parse_config(sys.argv[1])

    EXTRA_FLAGS=''
    if cfg.get('SLURM_PREEMPTABLE',False):
        EXTRA_FLAGS += '#SBATCH --qos=preemptable\n'
    if cfg.get('SLURM_NODELIST',False):
        EXTRA_FLAGS += f'#SBATCH --nodelist="{cfg["SLURM_NODELIST"]}"\n'

    if cfg['CLUSTER_TYPE'] == 'slurm':
        script_batch = TEMPLATE_slurm % (cfg['SLURM_PARTITION'],
                                         cfg['SLURM_ACCOUNT'],
                                         cfg['JOB_LOG_DIR'],
                                         cfg['JOB_LOG_DIR'],
                                         cfg['JOB_NCPU'],
                                         round(cfg['JOB_MEM']/cfg['JOB_NCPU']),
                                         cfg['JOB_TIME'],
                                         cfg['NJOBS_TOTAL'],
                                         cfg['SLURM_NJOBS_CONCURRENT'],
                                         EXTRA_FLAGS,
                                        )


    elif cfg['CLUSTER_TYPE'] == 'condor':
        jt = datetime.strptime(cfg['JOB_TIME'], '%H:%M:%S')
        total_seconds = jt.second + jt.minute * 60 + jt.hour * 3600
        script_batch = TEMPLATE_condor % (os.path.join(cfg['WCPROD_WORK_DIR'],cfg['EXECUTABLE']),
                                          cfg['JOB_LOG_DIR'],
                                          cfg['JOB_LOG_DIR'],
                                          cfg['JOB_LOG_DIR'],
                                          cfg['WCPROD_WORK_DIR'],
                                          cfg['JOB_PRIORITY'],
                                          cfg['JOB_NCPU'],
                                          round(cfg['JOB_MEM']/cfg['JOB_NCPU']),
                                          cfg['JOB_DISK_SPACE'],
                                          total_seconds,
                                          cfg['NJOBS_TOTAL'],
                                         )


    script = TEMPLATE_job_script % (cfg['WCPROD_WORK_DIR'],
        cfg['WCPROD_DB_FILE'],
        cfg['WCPROD_PROJECT'],
        cfg['WCPROD_NPHOTONS'],
        cfg['WCPROD_NSUBEVENTS'],
        cfg['WCPROD_NEVENTS'],
        os.path.join(cfg['WCPROD_STORAGE_ROOT'],cfg['WCPROD_PROJECT']),
        cfg['WCSIM_HOME'],
        cfg['CLUSTER_NAME'],
        cfg['WCPROD_NLOOPS'],
        cfg['BIND_PATH'],
        cfg['CONTAINER'],
        cfg['BIND_PATH'],                         
        cfg['CONTAINER'],
        cfg['BIND_PATH'],
        cfg['CONTAINER'],
        cfg['BIND_PATH'],
        cfg['CONTAINER'],
        cfg['BIND_PATH'],
        cfg['CONTAINER'],
        )

    if cfg['CLUSTER_TYPE'] == 'slurm':
        with open('run_voxel_slac.sh','w') as f:
            f.write(script_batch)
            f.write(script)

    elif cfg['CLUSTER_TYPE'] == 'condor':
        executable = os.path.join(cfg['WCPROD_WORK_DIR'],cfg['EXECUTABLE'])
        with open('run_voxel_condor.sub','w') as f:
            f.write(script_batch)
        with open(executable,'w') as f:
            f.write("#!/bin/bash\n")
            f.write(script)

if __name__ == '__main__':
    main()
