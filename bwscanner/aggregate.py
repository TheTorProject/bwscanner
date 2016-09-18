#!/usr/bin/env python

import json
from os.path import walk, join
from stem import connection, DescriptorUnavailable

def getjsonblobs(blobtarget, dirname, fnames):
    for fname in fnames:
        f = open(join(dirname, fname), 'r')
        try:
            for y in json.load(f):
                blobtarget.append(dict(y))
            f.close()
        except ValueError, e:
            print e

bloblist = []
walk('.', getjsonblobs, bloblist)

measurements = {}
failures = {}
for d in bloblist:
    for relay in d['path']:
        if 'failure' in d:
            if relay not in failures:
                failures[relay] = [d]
            else:
                failures[relay].append(d)
        else:
            if relay not in measurements:
                measurements[relay] = [d['circ_bw']]
            else:
                measurements[relay].append(d['circ_bw'])

# get a tor controller connection, to obtain consensus bandwidth values
tor_connection = connection.connect() # TODO: parametize or read from config...

# ensure that we have server descriptors available
if tor_connection.get_conf("UseMicroDescriptors") in ("auto", "1"):
    tor_connection.set_conf("UseMicroDescriptors", "0")
if tor_connection.get_conf("FetchUselessDescriptors") in ("auto", "1"):
    tor_connection.set_conf("FetchUselessDescriptors", "1")
if not tor_connection.get_conf("FetchDirInfoEarly"):
    tor_connection.set_conf("FetchDirInfoEarly", "1")
if not tor_connection.get_conf("FetchDirInfoExtraEarly"):
    tor_connection.set_conf("FetchDirInfoExtraEarly", "1")

# FIXME: how do we know when all these things are downloaded??

for relay in measurements.keys():
    mean_bw = sum(measurements[relay])/len(measurements[relay])
    filtered_bws = filter(lambda x: x >= mean_bw, measurements[relay])
    if len(filtered_bws) < 5: continue
    filt_bw = sum(filtered_bws)/len(filtered_bws)
    try:
        ns_bw = tor_connection.get_network_status(relay.strip('$')).bandwidth
        server_descriptor = tor_connection.get_server_descriptor(relay.strip('$'))
    except DescriptorUnavailable:
        continue # skip it for now
    nickname = server_descriptor.nickname
    desc_bw  = (server_descriptor.average_bandwidth, server_descriptor.burst_bandwidth,
                      server_descriptor.observed_bandwidth)

    if relay in failures and relay in measurements and len(failures) + len(measurements) >5:
        num_failures = len(failures[relay])
        num_measurements = len(measurements[relay])
        circ_fail_rate = 1.0*num_failures/(num_measurements + num_failures)
    else:
        circ_fail_rate = 0.0

    desc_bw = desc_bw[0] # average_bandwidth
    to_aggregate_py= "node_id={} nick={} strm_bw={} filt_bw={} circ_fail_rate={} desc_bw={} ns_bw={}"
    print to_aggregate_py.format(relay, nickname, mean_bw, filt_bw, circ_fail_rate, desc_bw, ns_bw)
