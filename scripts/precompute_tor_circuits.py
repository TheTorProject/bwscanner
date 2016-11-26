#!/usr/bin/env python
"""
precompute circuit permutations.
this is used to test the various
shuffle generators
"""

import click
import sys
import hashlib
import os

from stem.descriptor import parse_file

from bwscanner.partition_shuffle import lazy2HopCircuitGenerator
from bwscanner.partition_to_pair import to_pair_circuit_generator


def get_router_list_from_consensus(consensus):
    """
    arguments
        tor_state is a txtorcon TorState object
        consensus_file is a file containing a tor network-status-consensus-3 document
    returns
        a list of router fingerprints
    """
    routers = []
    with open(consensus, 'rb') as consensus_file:
        for relay in parse_file(consensus_file):
            if relay is not None and relay.fingerprint is not None:
                routers.append(relay.fingerprint)
            if len(routers) == 0:
                print "failed to parse consensus file"
                sys.exit(1)
    return routers

def get_router_list_from_file(relay_list_file):
    """
    arguments
        tor_state is a txtorcon TorState object
        relay_list_file is a file containing one Tor relay fingerprint per line
    returns
        a list of router fingerprints
    """
    routers = []
    with open(relay_list_file, "r") as rf:
        relay_lines = rf.read()
    for relay_line in relay_lines.split():
        router = relay_line
        routers.append(router)
    return routers


@click.command()
@click.option('--relay-list', default=None, type=str, help="file containing list of tor relay fingerprints, one per line")
@click.option('--consensus', default=None, type=str, help="file containing tor consensus document, network-status-consensus-3 1.0")
@click.option('--secret', default=None, type=str, help="secret")
@click.option('--partitions', default=None, type=int, help="total number of permuation partitions")
@click.option('--this-partition', default=None, type=int, help="which partition to scan")
def main(relay_list, consensus, secret, partitions, this_partition):

    if consensus is not None:
        relays = get_router_list_from_consensus(consensus)
    elif relay_list is not None:
        relays = get_router_list_from_file(relay_list)
    else:
        pass  # XXX todo: print usage

    consensus = ""
    for relay in relays:
        consensus += relay + ","
    consensus_hash = hashlib.sha256(consensus).digest()
    shared_secret_hash = hashlib.sha256(secret).digest()
    key = hashlib.pbkdf2_hmac('sha256', consensus_hash, shared_secret_hash, iterations=1)
    circuit_generator = lazy2HopCircuitGenerator(relays, this_partition, partitions, key)
    #key = os.urandom(208)
    #circuit_generator = to_pair_circuit_generator(relays, this_partition, partitions, key)

    while True:
        route = circuit_generator.next()
        print route
    

if __name__ == '__main__':
    main()
