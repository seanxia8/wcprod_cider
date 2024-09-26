#!/usr/bin/python3
import sys,os
import yaml
import wcprod

TEMPLATE='''#!/bin/bash
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

# Set-up a work dir
export WORKDIR=%s
mkdir -p $WORKDIR
cd $WORKDIR

# Generate a configuration file

if [ ! -f setup_job.yaml ]; then
    echo "
    DBFile:   %s
    Project:  %s
    NPhotons: %s
    NEvents:  %s
    Storage:  %s
    ROOT_SETUP: /src/root/install/bin/thisroot.sh
    WCSIM_HOME: %s
    WCSIM_ENV: /src/scripts/sourceme.sh
    Rebin_DBfile: %s
    WC_rmax: %f
    WC_zmax: %f
    Rebin_gap_space: %f
    Rebin_gap_angle: %f
    Rebin_n_bins_phi0: %f
    Num_shards: %d
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
 echo "Rebin"
 echo `date` && echo `date` >> log.txt  2>&1
 singularity exec %s %s ./run_rebin.sh >> log.txt  2>&1  

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
    keywords = ['WCPROD_STORAGE_ROOT','WCPROD_WORK_DIR','WCPROD_DB_FILE',
                'WCPROD_PROJECT','WCPROD_NEVENTS','WCPROD_NPHOTONS','WCPROD_NLOOPS',
                'SLURM_LOG_DIR','SLURM_TIME','SLURM_MEM',
                'SLURM_ACCOUNT','SLURM_PARTITION','SLURM_PREEMPTABLE',
                'SLURM_NCPU','SLURM_NJOBS_TOTAL','SLURM_NJOBS_CONCURRENT',
                'CONTAINER_WCSIM','CONTAINER_WCPROD', 'WCSIM_HOME',
                'REBIN_DB_FILE', 'WC_RMAX','WC_ZMAX',
                'REBIN_GAP_SPACE', 'REBIN_GAP_ANGLE', 'REBIN_N_BINS_PHI0', 'NUM_SHARDS']

    for key in keywords:
        if not key in cfg.keys():
            print('ERROR: config missing a keyword',key)
            sys.exit(1)
    
    for key in ['CONTAINER_WCSIM','CONTAINER_WCPROD','WCPROD_DB_FILE']:
        if not os.path.isfile(cfg[key]):
            print(f"ERROR: a container missing '{cfg[key]}'")
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
        cfg['WCPROD_WORK_DIR'],
        cfg['WCPROD_DB_FILE'],
        cfg['WCPROD_PROJECT'],
        cfg['WCPROD_NPHOTONS'],
        cfg['WCPROD_NEVENTS'],
        os.path.join(cfg['WCPROD_STORAGE_ROOT'],cfg['WCPROD_PROJECT']),
        cfg['WCSIM_HOME'],
        cfg['REBIN_DB_FILE'],
        cfg['WC_RMAX'],
        cfg['WC_ZMAX'],
        cfg['REBIN_GAP_SPACE'],
        cfg['REBIN_GAP_ANGLE'],
        cfg['REBIN_N_BINS_PHI0'],
        cfg['NUM_SHARDS'],
        cfg['WCPROD_NLOOPS'],
        cfg['BIND_PATH'],
        cfg['CONTAINER_WCPROD'],
        cfg['BIND_PATH'],                         
        cfg['CONTAINER_WCSIM'],
        cfg['BIND_PATH'],
        cfg['CONTAINER_WCSIM'],
        cfg['BIND_PATH'],
        cfg['CONTAINER_WCPROD'],
        cfg['BIND_PATH'],
        cfg['CONTAINER_WCSIM'],
        cfg['BIND_PATH'],
        cfg['CONTAINER_WCSIM'],
        )

    with open('run_voxel_slac.sh','w') as f:
        f.write(script)

if __name__ == '__main__':
    main()
