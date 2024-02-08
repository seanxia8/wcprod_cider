from skbuild import setup
import argparse

import io,os,sys
this_directory = os.path.abspath(os.path.dirname(__file__))
with io.open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="wcprod",
    version="0.1",
    author=['Kazuhiro Terao'],
    description='Database for the CIDeR simulation production for Water Cherenkov detectors',
    license='MIT',
    scripts=['cli/wcprod'],
    packages=['wcprod'],
    install_requires=[
        'numpy',
        'scikit-build',
        'plotly',
    ],
    long_description=long_description,
    long_description_content_type='text/markdown',
)
