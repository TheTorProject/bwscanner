"""
This scanner is used detect partition Tor network partitions.
Relays which cannot connect to each other are bad for Tor network health
and it may indicate that a partitioning attack is being performed.
"""
import time, hashlib
from twisted.internet import defer
from txtorcon.circuit import build_timeout_circuit, CircuitBuildTimedOutError

from bwscanner.writer import ResultSink
from bwscanner.partition_shuffle import lazy2HopCircuitGenerator


class ProbeAll2HopCircuits(object):

    def __init__(self, state,
                 clock,
                 log_dir,
                 stopped,
                 relays,
                 shared_secret,
                 partitions,
                 this_partition,
                 build_duration,
                 circuit_timeout):
        """
        state: the txtorcon state object
        clock: this argument is normally the twisted global reactor object but
        unit tests might set this to a clock object which can time travel for faster testing.
        log_dir: the directory to write log files
        stopped: callable to call when done
        partitions: the number of partitions to use for processing the set of circuits
        this_partition: which partition of circuit we will process
        build_duration: build a new circuit every specified duration
        circuit_timeout: circuit build timeout duration
        """
        self.state = state
        self.clock = clock
        self.log_dir = log_dir
        self.stopped = stopped
        self.relays = relays
        self.shared_secret = shared_secret
        self.partitions = partitions
        self.this_partition = this_partition

        self.lazy_tail = defer.succeed(None)

        consensus_hash = hashlib.sha256([str(relay) for relay in relays].join(",")).digest()
        shared_secret_hash = hashlib.sha256(shared_secret).digest()
        prng_seed = hashlib.pbkdf2_hmac(
            'sha256',
            consensus_hash,
            shared_secret_hash, 
            iterations=1 )

        self.circuits = lazy2HopCircuitGenerator(relays, this_partition, partitions, prng_seed)
        self.tasks = []

        # XXX adjust me
        self.result_sink = ResultSink(log_dir, chunk_size=1000)
        self.circuit_life_duration = circuit_timeout
        self.circuit_build_duration = build_duration

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
            # XXX todo: remove logging of successful circuit build
            time_end = self.now()
            self.result_sink.send({"time_start": time_start,
                                   "time_end": time_end,
                                   "path": serialized_route,
                                   "status": "ok",
                                   "info": None})
            return None

        def circuit_build_timeout(f):
            f.trap(CircuitBuildTimedOutError)
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
        d = build_timeout_circuit(self.state, self.clock, route, self.circuit_life_duration)
        d.addCallback(circuit_build_report) # XXX todo: remove logging of successful circuit build
        d.addErrback(circuit_build_timeout)
        d.addErrback(circuit_build_failure)
        self.tasks.append(d)

    def start(self):
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
