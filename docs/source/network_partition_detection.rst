

====================================
 Scanning for Tor network partition
====================================


introduction
------------

Here we present the idea of actively scanning the Tor network for
partitions, however this is a fundametnally flawed design because
network adversaries can possibly detect our scan and influence the
results.  It would be better to passively receive statistics from each
Tor relay in the network and use that data to measure bandwidth and
detect network partitions.

The partition scanner will produce some inaccurate results for other
reasons as well, for instance if A cannot connect to B but B can
connect to relay A then our circuit build test for A -> B may still
result in success if B has a prior established TCP connection to
relay A.

The partition scanner uses a CPU and memory efficient algorithm for
generating 2-hop circuit permutations that include both directions
e.g. A->B && B->A. This means that the size of our set of circuits is::

  (n**2 - n) where n is the number of relays in the set

The scanner permutation generator also uses a partitioning scheme so
that the scan can be parallelized with many worker nodes scanning
their own partition of the shuffled set of 2-hop circuits.


cli usage
---------

Usage: detect_partitions.py [OPTIONS]::

 Options:
  --tor-control TEXT           tor control port as twisted endpoint descriptor
                               string
  --tor-data TEXT              launch tor data directory
  --log-dir TEXT               log directory
  --relay-list TEXT            file containing list of tor relay fingerprints,
                               one per line
  --consensus TEXT             file containing tor consensus document,
                               network-status-consensus-3 1.0
  --secret TEXT                secret
  --partitions INTEGER         total number of permuation partitions
  --this-partition INTEGER     which partition to scan
  --build-duration FLOAT       circuit build duration
  --circuit-timeout FLOAT      circuit build timeout
  --prometheus-port INTEGER    prometheus port to listen on
  --prometheus-interface TEXT  prometheus interface to listen on
  --help                       Show this message and exit.


The ``--consensus`` option can be used to specify a consensus file, for instance
one of these:

https://collector.torproject.org/recent/relay-descriptors/consensuses/

CLI example::

  wget https://collector.torproject.org/recent/relay-descriptors/consensuses/2016-10-19-21-00-00-consensus

  ./scripts/detect_partitions.py --tor-control tcp:127.0.0.1:9051 --log-dir /home/human \
  --secret my_shuffle_secret --partitions 40 --this-partition 0 --build-duration .05 \
  --circuit-timeout 10 --prometheus-port 8080 --prometheus-interface 127.0.0.1 \
  --consensus 2016-10-19-21-00-00-consensus
