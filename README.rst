BWScanner
=========

.. image:: https://travis-ci.org/TheTorProject/bwscanner.svg?branch=develop
    :target: https://travis-ci.org/TheTorProject/bwscanner

.. image:: https://coveralls.io/repos/github/TheTorProject/bwscanner/badge.svg?branch=develop :target: https://coveralls.io/github/TheTorProject/bwscanner?branch=develop

BWScanner is a tool for measuring the bandwidth of Tor relays. Its aim is to replace the existing Torflow system.

This project is still under active development and is not ready for active use or production deployment yet.


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
