#!/bin/bash
workdir=${PWD}

for i in {2..648}; do
    if [ ! -f "${wordir}/job_yaml/job_voxel_${i}.yaml" ]; then
      cp "${workdir}/job_yaml/job_voxel.yaml" "${workdir}/job_yaml/job_voxel_${i}.yaml"

    fi

    echo "Processing $i"
    sed -i 's/^[[:space:]]*CONFIG_ID:[[:space:]]*[0-9]\+$/CONFIG_ID: '${i}'/' "${workdir}/job_yaml/job_voxel_${i}.yaml"

    mkdir -p "${workdir}/job_output/voxel_config_${i}"
    cd "${workdir}/job_output/voxel_config_${i}"

    singularity exec -B /sdf ~/sdf-data/sif/cider-dataprod_24.10.28.sif bash -c "wcprod_gen_voxel.py ${workdir}/job_yaml/job_voxel_${i}.yaml"
    chmod +x "./run_voxel_slac.sh"

    //sbatch "./run_voxel_slac.sh"

    cd "${workdir}"
done