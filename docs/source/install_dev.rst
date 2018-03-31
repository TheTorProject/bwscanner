Installation for development
=============================

It is recommended to install ``bwscanner`` in a ``virtualenv``

Check `virtualenv installation <https://virtualenv.pypa.io/en/latest/installation.html`_.
In Debian::

    sudo apt install python-virtualenv

Create a virtual environment::

    mkdir ~/.virtualenvs
    virtualenv ~/.virtualenvs/bwscannerenv
    source ~/.virtualenvs/bwscannerenv/bin/activate

Get ``bwscanner`` sources::

    git clone https://github.com/TheTorProject/bwscanner

Install it in development mode::

    cd bwscanner
    pip install -e .

Running tests
----------------

Unit and integration tests are run automatically for each pull request. The tests must pass before code will be merged. Tox is used to run the tests reproducibly in your development environment.

Tox can be used to create new Python virtual environments with a reproducible state and to run all the tests.

Install the test depenencies:

.. code:: bash

    pip install -e .[test]

The integration tests are run against a local Tor network which is managed by ``chutney``. You can start ``chutney`` as follows:


.. code:: bash

    ./test/scripts/install-chutney.sh

The bandwidth scanner needs to be able to connect to a Tor control port to interact with the network. If using ``chutney`` the port ``8021`` should work. Tests are run by simply calling ``tox``.

.. code:: bash

    export CHUTNEY_CONTROL_PORT=8021
    tox

To stop and start ``chutney``, run::

    cd chutney
    ./chutney stop networks/basic-025
    ./chutney start networks/basic-025
    cd ..
