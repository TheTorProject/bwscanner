import os.path
import json  # XXX replace with bson
import time

from twisted.internet import defer, threads

from bwscanner.circuit import FullyConnected



class ProbeAll2HopCircuits(object):

    def __init__(self, state, clock, log_dir, stopped, partitions=1, this_partition=0):
        """
        state: the txtorcon state object
        clock: this argument is normally the twisted global reactor object but
        unit tests might set this to a clock object which can time travel for
        speeding up tests.
        log_dir: the directory to write log files
        stopped: callable to call when done
        partitions: the number of partitions to use for processing the
        set of circuits
        this_partition: which partition of circuit we will process
        """
        self.state = state
        self.clock = clock
        self.log_dir = log_dir
        self.stopped = stopped
        self.partitions = partitions
        self.this_partition = this_partition

        self.lazy_tail = defer.succeed(None)
        self.circuits = FullyConnected(self.state)
        self.routers = self.state.routers
        self.run_scan()
        self.tasks = []

        # XXX adjust me
        self.result_sink = ResultSink(log_dir, chunk_size=1000)
        self.circuit_life_duration = 10
        self.circuit_build_duration = .2

    def now(self):
        return 1000 * time.time()

    def serialize_route(self, route):
        """
        Serialize a route.
        """
        route_list = []
        for router in route:
            route_list.append("%r" % (router,))
        return route_list

    def build_circuit(self, route):
        """
        Build a tor circuit using the specified path of relays
        and a timeout.
        """
        serialized_route = self.serialize_route(route)

        def circuit_build_report(result):
            time_end = self.now()
            self.result_sink.send({"time_start": time_start,
                                   "time_end": time_end,
                                   "path": serialized_route,
                                   "status": "ok",
                                   "info": None})
            return None

        def circuit_build_timeout(f):
            # XXX: CircuitBuildTimedOutError doesn't exist?
            # f.trap(CircuitBuildTimedOutError)
            time_end = self.now()
            self.result_sink.send({"time_start": time_start,
                                   "time_end": time_end,
                                   "path": serialized_route,
                                   "status": "timeout",
                                   "info": None})
            return None

        def circuit_build_failure(f):
            time_end = self.now()
            self.result_sink.send({"time_start": time_start,
                                   "time_end": time_end,
                                   "path": serialized_route,
                                   "status": "failure",
                                   "info": None})
            return None

        time_start = self.now()
        # XXX build_timeout_circuit doesn't yet exist in upstream txtorcon
        d = self.state.build_circuit(route)
        self.clock.callLater(self.circuit_life_duration, d.cancel)
        d.addCallback(circuit_build_report)
        d.addErrback(circuit_build_timeout)
        d.addErrback(circuit_build_failure)
        self.tasks.append(d)

    def run_scan(self):
        def pop():
            try:
                self.build_circuit(self.circuits.next())
            except StopIteration:
                dl = defer.DeferredList(self.tasks)
                dl.addCallback(lambda ign: self.result_sink.end_flush())
                dl.addCallback(lambda ign: self.stopped())
                self.call_id.cancel()
            else:
                self.call_id = self.clock.callLater(self.circuit_build_duration, pop)
        self.clock.callLater(0, pop)
