.. photonlib documentation master file, created by
   sphinx-quickstart on Wed Oct 26 19:52:12 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to photonlib's documentation!
===========================================
This software is used to facilitate a large-scale simulation sample production for `optical SIREN model <https://github.com/CIDeR-ML/>`_. Training of this model requires to sample positions and directions of a photon everywhere and every direction in the detector. The number of samples (job configuration) can easily reach hundreds of millions. Book-keeping of the data production is implemented using sqlite database and automated job submission scripts in this software which repository can be found `here <https://github.com/CIDeR-ML/wcprod>`_.
to interface a photon library file used for Liquid Argon Time Projection Chamber (LArTPC) detectors. For the installation, tutorial notebooks, and learning what photon library is, please see the `software repository <https://github.com/CIDeR-ML/photonlib>`_.


Getting started
---------------

You can find a quick guide to get started below.

Install ``photonlib``
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   git clone https://github.com/cider-ml/wcprod
   cd wcprod
   pip install . --user


You can install to your system path by omitting ``--user`` flag. 
If you used ``--user`` flag to install in your personal space, assuming ``$HOME``, you may have to export ``$PATH`` environment variable to find executables.

.. code-block:: bash
   
   export PATH=$HOME/.local/bin:$PATH

Download data file
^^^^^^^^^^^^^^^^^^

.. toctree::
   :maxdepth: 2
   :caption: Package Reference
   :glob:

   wcprod <wcprod>

.. Indices and tables
.. ==================

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
