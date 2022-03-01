BWScanner
=========

.. image:: https://travis-ci.org/TheTorProject/bwscanner.svg?branch=develop
    :target: https://travis-ci.org/TheTorProject/bwscanner

.. image:: https://coveralls.io/repos/github/TheTorProject/bwscanner/badge.svg?branch=develop&reload=1
    :target: https://coveralls.io/github/TheTorProject/bwscanner?branch=develop

.. important:: This software is deprecated in favor of
   `sbws <https://gitlab.torproject.org/tpo/network-health/sbws>`_

BWScanner is a tool for measuring the bandwidth of Tor relays. Its aim is to replace the existing Torflow system.

This project is still under active development and is not ready for active use or production deployment yet.


Installation
------------

BWScanner is not yet compatible with Python 3 due to the `txsocksx ` dependency.

In Debian/Ubuntu systems, you can install Python 2 and other systems
requirements running:

.. code:: bash

    sudo apt install python2.7 python2.7-dev

The bandwidth scanner and its dependencies can be installed as follows:

.. code:: bash

    git clone https://github.com/TheTorProject/bwscanner.git
    cd bwscanner
    python setup.py install

In case your system is using Python 3 by default, you need to run Python 2
explicitely, changing last line by:

.. code:: bash

    python2.7 setup.py install


Running
-------

After installation the ``bwscan`` tool should be available in your path. This tool has a number of subcommands for running scans and for aggregating the collected data for use by the bandwidth authorities.


Collecting bandwidth measurements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``--partitions`` option can be used to split the consensus into subsets of relays which can be scanned on different machines. The results can later be combined during the measurement aggregation step.

.. code:: bash

    bwscan scan


Aggregating scan results
~~~~~~~~~~~~~~~~~~~~~~~~

This command will aggregate the data for the latest five completed scans.

.. code:: bash

    bwscan aggregate -n 5


The final aggregation script is not yet integrated with the CLI. It should be called with the path to the directory containing the most recent aggregated data:

.. code:: bash

    python scripts/aggregate.py ~/.config/bwscanner/measurements/1474278776

Contact
--------

#bwscanner at irc.oftc.net

License
--------

Copyright 2016 Aaron Gibson, Donncha Ó Cearbhaill, David Stainton,
Copyright 2018 Aaron Gibson, juga, Donncha Ó Cearbhaill
under the terms of the `GPLv2 <https://www.gnu.org/licenses/>`__ license.
