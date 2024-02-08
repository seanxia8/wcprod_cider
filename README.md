[![Documentation Status](https://readthedocs.org/projects/wcprod/badge/?version=latest)](https://wcprod.readthedocs.io/en/latest/?badge=latest)

# wcprod
This is a python API to use data production tools for generating a large-scale photon dataset in CIDeR-ML collaboration.

Training of "Optical SIREN" model for a Water Cherenkov detector requires serious statistics of photon simulation.
A typical dataset requires 100E6 photon simulated at 10-100E6 positions/directions.
This requires running simulations over many processes (>>10k) and considerable effort in book-keeping of managing processes and output files.
`wcprod` aims to address this challenge of process management in a large-scale sample production.

For users, you might find a complimentary documentation at the [ReadTheDocs](https://wcprod.readthedocs.io/en/latest/). 

For developers, make sure you read the [Contribution Guide](/contributing.md).

## Installation
Once `git clone` this repository, go inside and:
```
pip install .
```

Tutorial materials are gathered in a publicly accessible folder in [this google drive link](https://drive.google.com/drive/folders/1IjRUMMVW7aiGWGcZFGRb9nT8dCRVYolE?usp=share_link).

### Creating a production database
Coming soon
