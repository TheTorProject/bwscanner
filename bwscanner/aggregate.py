from __future__ import division
import os
import glob
import json

from twisted.internet.defer import inlineCallbacks
from stem.descriptor.server_descriptor import RelayDescriptor
from stem.descriptor.router_status_entry import RouterStatusEntryV3

from bwscanner.logger import log


def load_json_measurements(directory):
    for name in glob.glob(os.path.join(directory, "*.json")):
        with open(os.path.join(directory, name), 'r') as json_file:
            try:
                for y in json.load(json_file):
                    yield dict(y)
            except ValueError:
                log.error("Error reading JSON measurement file")


def load_measurement_data(measurement_directory):
    measurements, failures = {}, {}
    for item in load_json_measurements(measurement_directory):
        for relay in item['path']:
            relay_fp = relay.lstrip("%")
            if 'failure' in item:
                failures.setdefault(relay_fp, []).append(item)
            else:
                measurements.setdefault(relay_fp, []).append(item['circ_bw'])

    log.info("Loaded {success} successful measurements and {fail} failures.",
             success=len(measurements), fail=len(failures))
    return measurements, failures


@inlineCallbacks
def write_aggregate_data(tor, measurement_dir, file_name="aggregate_measurements"):
    # Get a tor controller connection, to obtain consensus bandwidth values
    # XXX: Should this data be saved from the consensus at scan time.

    # FIXME: how do we know when all these things are downloaded??
    log.info("Loading JSON measurement files")
    measurements, failures = load_measurement_data(measurement_dir)

    aggregate_file = open(os.path.join(measurement_dir, file_name), 'w')

    log.info("Processing the loaded bandwidth measurements")
    for relay_fp in measurements.keys():
        log.debug("Aggregating measurements for {relay}", relay=relay_fp)

        mean_bw = sum(measurements[relay_fp]) / len(measurements[relay_fp])

        # Calculated the "filtered bandwidth"
        filtered_bws = [bw for bw in measurements[relay_fp] if bw >= mean_bw]
        if filtered_bws:
            mean_filtered_bw = sum(filtered_bws) / len(filtered_bws)
        if not filtered_bws or mean_filtered_bw <= 0:
            log.debug("Could not calculate a valid filtered bandwidth, skipping relay.")
            continue

        routerstatus_info = yield tor.protocol.get_info_raw('ns/id/' + relay_fp)
        descriptor_info = yield tor.protocol.get_info_raw('desc/id/' + relay_fp)
        relay_routerstatus = RouterStatusEntryV3(routerstatus_info)
        relay_descriptor = RelayDescriptor(descriptor_info)

        ns_bw = relay_routerstatus.bandwidth
        nickname = relay_descriptor.nickname

        if (relay_fp in failures and relay_fp in measurements and
                (len(failures) + len(measurements)) > 5):
            num_failures = len(failures[relay_fp])
            num_measurements = len(measurements[relay_fp])
            circ_fail_rate = num_failures / (num_measurements + num_failures)
        else:
            log.debug("Not enough measurements to calculate the circuit fail rate.")
            circ_fail_rate = 0.0

        desc_bw = relay_descriptor.average_bandwidth
        line_format = ("node_id={} nick={} strm_bw={} filt_bw={} circ_fail_rate={} "
                       "desc_bw={} ns_bw={}\n")

        aggregate_file.write(line_format.format(relay_fp, nickname, mean_bw, mean_filtered_bw,
                                                circ_fail_rate, desc_bw, ns_bw))

    aggregate_file.close()
    log.info("Finished outputting the aggregated measurements.")
