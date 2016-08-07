import time

from stem.descriptor.server_descriptor import ServerDescriptor
from stem.descriptor.networkstatus import RouterStatusEntryV3

from twisted.internet import defer
from twisted.python import log

from bwscanner.attacher import SOCKSClientStreamAttacher
from bwscanner.circuit import TwoHop
from bwscanner.fetcher import OnionRoutedAgent, cancellableReadBody
from bwscanner.writer import ResultSink

# defer.setDebugging(True)


class DownloadIncomplete(Exception):
    pass


class BwScan(object):
    def __init__(self, state, clock, log_dir, **kwargs):
        """
        state: the txtorcon state object
        clock: this argument is normally the twisted global reactor object but
        unit tests might set this to a clock object which can time travel for
        speeding up tests.
        log_dir: the directory to write log files
        partitions: the number of partitions to use for processing the
        set of circuits
        this_partition: which partition of circuit we will process
        """
        self.state = state
        self.clock = clock
        self.log_dir = log_dir
        self.partitions = kwargs.get('partitions', 1)
        self.this_partition = kwargs.get('this_partition', 0)
        self.scan_continuous = kwargs.get('scan_continuous', False)
        self.request_timeout = kwargs.get('request_timeout', 60)
        self.circuit_launch_delay = kwargs.get('circuit_launch_delay', .2)

        self.tasks = []
        self.circuits = None
        self.baseurl = 'https://bwauth.torproject.org/bwauth.torproject.org'
        self.bw_files = {
            64*1024: "64M",
            32*1024: "32M",
            16*1024: "16M",
            8*1024: "8M",
            4*1024: "4M",
            2*1024: "2M",
        }

        self.result_sink = ResultSink(log_dir, chunk_size=10)

        # Add a stream attacher
        self.state.set_attacher(SOCKSClientStreamAttacher(self.state), clock)

    def now(self):
        return 1000 * time.time()

    def choose_file_size(self, path):
        avg_bw = sum([r.bandwidth for r in path])/len(path)
        for size in sorted(self.bw_files.keys()):
            if avg_bw*5 < size:
                return size
        return max(self.bw_files.keys())

    def choose_url(self, path):
        return self.baseurl + '/' + self.bw_files[self.choose_file_size(path)]

    def run_scan(self):
        all_done = defer.Deferred()
        if self.scan_continuous:
            all_done.addCallback(lambda ign: self.run_scan())
        self.circuits = TwoHop(self.state, partitions=self.partitions,
                               this_partition=self.this_partition)

        def scan_over_next_circuit():
            try:
                self.fetch(self.circuits.next())
            except StopIteration:
                # All circuit measurement tasks have been setup. Now wait for
                # all tasks to complete before writing results, and firing
                # the all_done deferred.
                task_list = defer.DeferredList(self.tasks)
                task_list.addCallback(lambda _: self.result_sink.end_flush())
                task_list.chainDeferred(all_done)
            else:
                # We have circuits left, schedule scan on the next circuit
                self.clock.callLater(self.circuit_launch_delay,
                                     scan_over_next_circuit)

        # Scan the first circuit
        self.clock.callLater(0, scan_over_next_circuit)
        return all_done

    def fetch(self, path):
        url = self.choose_url(path)
        assert None not in path
        log.msg('Downloading {} over {}, {}'.format(url, path[0].id_hex, path[-1].id_hex))
        file_size = self.choose_file_size(path)
        time_start = self.now()

        @defer.inlineCallbacks
        def get_circuit_bw(result):
            time_end = self.now()
            if len(result) < file_size:
                raise DownloadIncomplete
            report = dict()
            report['time_end'] = time_end
            report['time_start'] = time_start
            report['circ_bw'] = (len(result) * 1000) / (report['time_end'] - report['time_start'])
            report['path'] = [r.id_hex for r in path]

            # We need to wait for these deferreds to be ready, we can't serialize
            # deferreds.
            report['path_desc_bws'] = []
            report['path_ns_bws'] = []
            for relay in path:
                report['path_desc_bws'].append((yield self.get_r_desc_bw(relay)))
                report['path_ns_bws'].append((yield self.get_r_ns_bw(relay)))
            report['path_bws'] = [r.bandwidth for r in path]
            log.msg("Download successful for router %s." % path[0].id_hex)
            defer.returnValue(report)

        def circ_failure(failure):
            time_end = self.now()
            report = dict()
            report['time_end'] = time_end
            report['time_start'] = time_start
            report['path'] = [r.id_hex for r in path]
            report['failure'] = failure.__repr__()
            log.msg("Download failed for router %s: %s." % (path[0].id_hex, report['failure']))
            return report

        def timeoutDeferred(deferred, timeout):
            def cancelDeferred(deferred):
                deferred.cancel()

            delayedCall = self.clock.callLater(timeout, cancelDeferred, deferred)

            def gotResult(result):
                if delayedCall.active():
                    delayedCall.cancel()
                return result
            deferred.addBoth(gotResult)

        agent = OnionRoutedAgent(self.clock, path=path, state=self.state)
        request = agent.request("GET", url)
        request.addCallback(cancellableReadBody)  # returns a readBody Deferred
        timeoutDeferred(request, self.request_timeout)
        request.addCallbacks(get_circuit_bw)
        request.addErrback(circ_failure)
        request.addCallback(self.result_sink.send)
        self.tasks.append(request)

    @defer.inlineCallbacks
    def get_r_ns_bw(self, router):
        """Fetch the NetworkStatus bandwidth values for this router from Tor via a ControlPort

        :param: router, txtorcon.router.Router
        :return: tuple of NetworkStatus bandwidth and Measured flag
        """

        raw_descriptor = yield self.state.protocol.get_info_raw('ns/id/{}'.format(router.id_hex))
        router_ns_entry = RouterStatusEntryV3(raw_descriptor)
        defer.returnValue((router_ns_entry.bandwidth, router_ns_entry.is_unmeasured))

    @defer.inlineCallbacks
    def get_r_desc_bw(self, router):
        """Fetch the ServerDescriptor bandwidth values for this router from Tor via a ControlPort

        :param: router, txtorcon.router.Router
        :return: triple of ServerDescriptor average_bandwidth, burst_bandwidth,
                 and observed_bandwidth.
        """

        raw_descriptor = yield self.state.protocol.get_info_raw('desc/id/{}'.format(router.id_hex))
        server_descriptor = ServerDescriptor(raw_descriptor)
        defer.returnValue((server_descriptor.average_bandwidth,
                           server_descriptor.burst_bandwidth,
                           server_descriptor.observed_bandwidth))
