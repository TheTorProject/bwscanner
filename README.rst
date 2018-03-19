BWScanner
=========

.. image:: https://travis-ci.org/TheTorProject/bwscanner.svg?branch=develop
    :target: https://travis-ci.org/TheTorProject/bwscanner

.. image:: https://coveralls.io/repos/github/TheTorProject/bwscanner/badge.svg?branch=develop&reload=1
    :target: https://coveralls.io/github/TheTorProject/bwscanner?branch=develop

BWScanner is a tool for measuring the bandwidth of Tor relays. Its aim is to replace the existing Torflow system.

This project is still under active development and is not ready for active use or production deployment yet.


Installation
------------

The bandwidth scanner and its dependencies can be installed as follows:

.. code:: bash

    git clone https://github.com/TheTorProject/bwscanner.git
    cd bwscanner
    python setup.py install

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


Development
-----------

Unit and integration tests are run automatically for each pull request. The tests must pass before code will be merged. Tox is used to run the tests reproducibly in your development environment.

Tox can be used to create new Python virtual environments with a reproducible state and to run all the tests.

.. code:: bash

    pip install tox
    git clone https://github.com/TheTorProject/bwscanner.git
    cd bwscanner

The integration tests are run against a local Tor network which is managed by ``chutney``. You can start ``chutney`` as follows:


.. code:: bash

    git clone https://git.torproject.org/chutney.git
    cd chutney
    ./chutney stop networks/basic-025
    ./chutney configure networks/basic-025
    ./chutney start networks/basic-025
    ./chutney status networks/basic-025
    cd ..

The bandwidth scanner needs to be able to connect to a Tor control port to interact with the network. If using ``chutney`` the port ``8021`` should work. Tests are run by simply calling ``tox``.

.. code:: bash

    cd bwscanner
    export CHUTNEY_CONTROL_PORT=8021
    tox

Contact
--------

#bwscanner at irc.oftc.net
