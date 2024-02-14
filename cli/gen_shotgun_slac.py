#!/usr/bin/python3
import sys,os
import yaml

TEMPLATE_MAIN='''#!/bin/bash
#SBATCH --job-name=dntp
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

# Set-up a work dir
export WORKDIR=${LSCRATCH}/workdir_${SLURM_JOB_ID}
mkdir -p $WORKDIR
cd $WORKDIR

# Generate a configuration file
echo "
DBFile:   /sdf/data/neutrino/wcprod/${1}/config.db
Project:  ${1}
NPhotons: ${2}
NEvents:  ${3}
Storage:  %s/${1}
WCSIM_BUILDDIR: ${WCSIMDIR}/build
ROOT_SETUP: /src/root/install/bin/thisroot.sh
" >> job.yaml

# Prepare for WCSim job
scp -r $WCSIMDIR/build/macros ./

echo `printenv` 

# Execute N times
for (( i=1;i<=$3;i++ ))
do

 echo "Starting: run counter $i"
 echo `date`
 singularity exec -B /sdf %s python3 setup_shotgun.py job.yaml

 echo "Running Geant4"
 echo `date`
 singularity run -B /sdf %s g4.mac 

 echo "Running check"
 echo `date`
 singularity run -B /sdf %s check.sh

 echo "Wrapping up"
 echo `date`
 singularity exec -B /sdf %s python3 job_shotgun.py wrapup.yaml

 echo "Finished!"
 echo `date`
done

echo "Exiting"
echo `date`
'''

def parse_config(cfg):
    if not os.path.isfile(cfg):
        print(f"Configuration yaml file '{cfg}' does not exist.")
        sys.exit(1)

    cfg = yaml.safe_load(open(cfg,'r').read())
    keywords = ['STORAGE_ROOT',
    'SLURM_LOG_DIR','SLURM_TIME','SLURM_MEM',
    'SLURM_ACCOUNT','SLURM_PARTITION',
    'SLURM_NCPU','SLURM_NJOBS_TOTAL','SLURM_NJOBS_CONCURRENT',
    'CONTAINER_WCSIM','CONTAINER_WCPROD']

    for key in keywords:
        if not key in cfg.keys():
            print('ERROR: config missing a keyword',key)
            sys.exit(1)

    for key in ['CONTAINER_WCSIM','CONTAINER_WCPROD']:
        if not os.path.isfile(cfg[key]):
            print(f"ERROR: a container missing '{cfg[key]}'")
            sys.exit(1)

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

    script = TEMPLATE % (cfg['SLURM_PARTITION'],
        cfg['SLURM_ACCOUNT'],
        cfg['SLURM_LOG_DIR'],
        cfg['SLURM_LOG_DIR'],
        cfg['SLURM_NCPU'],
        round(cfg['SLURM_MEM']/cfg['SLURM_NCPU']),
        cfg['SLURM_TIME'],
        cfg['SLURM_NJOBS_TOTAL'],
        cfg['SLURM_NJOBS_CONCURRENT'],
        EXTRA_FLAGS,
        cfg['STORAGE_ROOT'],
        cfg['CONTAINER_WCPROD'],
        cfg['CONTAINER_WCSIM'],
        cfg['CONTAINER_WCPROD'],
        )

    with open('run_shotgun_slac.sh','w') as f:
        f.write(script)
        

if __name__ == '__main__':
    main()











