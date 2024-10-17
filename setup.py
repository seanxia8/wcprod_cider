from setuptools import setup

import io,os,sys
this_directory = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="wcprod",
    version="0.2",
    author=['Kazuhiro Terao','Junjie Xia'],
    description='Database for the CIDeR simulation production for Water Cherenkov detectors',
    license='MIT',
    scripts=['cli/wcprod',
    'cli/wcprod_gen_shotgun_slac.py',
    'cli/wcprod_setup_shotgun.py',
    'cli/wcprod_wrapup_shotgun.py',
    'cli/wcprod_gen_voxel_slac.py',
    'cli/wcprod_gen_voxel.py',
    'cli/wcprod_setup_voxel.py',
    'cli/wcprod_wrapup_voxel.py',
    'cli/wcprod_list_config',
    'cli/wcprod_get_config'],
    packages=['wcprod'],
    include_package_data=True,
    package_data={'wcprod': ['config/*.yaml']},
    install_requires=[
        'numpy',
        'plotly',
    ],
    long_description=long_description,
    long_description_content_type='text/markdown',
)
