"""
This scanner is used detect partition Tor network partitions.
Relays which cannot connect to each other are bad for Tor network health
and it may indicate that a partitioning attack is being performed.
"""
import time

from twisted.internet.error import AlreadyCalled
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.web.server import Site
from twisted.web.resource import Resource

from txtorcon.circuit import build_timeout_circuit, CircuitBuildTimedOutError

from bwscanner.writer import ResultSink


try:
    from prometheus_client.twisted import MetricsResource
    from prometheus_client import Counter
    has_prometheus_client = True
except ImportError:
    has_prometheus_client = False

    def MetricsResource(*a, **kw):
        pass

    class MockCounter():
        def __init__(self, *a, **kw):
            pass

        def inc(self, *a, **kw):
            pass
    Counter = MockCounter


class ProbeAll2HopCircuits(object):

    def __init__(self, state, clock, log_dir, stopped, partitions,
                 this_partition, build_duration, circuit_timeout, circuit_generator,
                 log_chunk_size, max_concurrency,
                 prometheus_port=None, prometheus_interface=None):
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
        self.partitions = partitions
        self.this_partition = this_partition
        self.circuit_life_duration = circuit_timeout
        self.circuit_build_duration = build_duration
        self.circuits = circuit_generator
        self.prometheus_port = prometheus_port
        self.prometheus_interface = prometheus_interface
        self.log_chunk_size = log_chunk_size

        self.semaphore = defer.DeferredSemaphore(max_concurrency)
        self.lazy_tail = defer.succeed(None)
        self.tasks = {}


        # XXX adjust me
        self.result_sink = ResultSink(log_dir, chunk_size=log_chunk_size)

    def now(self):
        return 1000 * time.time()

    def serialize_route(self, route):
        """
        Serialize a route.
        """
        return "%s -> %s" % (route[0].id_hex, route[1].id_hex)

    def build_circuit(self, route):
        """
        Build a tor circuit using the specified path of relays
        and a timeout.
        """
        serialized_route = self.serialize_route(route)

        def circuit_build_success(circuit):
            self.count_success.inc()
            return circuit.close()

        def circuit_build_timeout(f):
            f.trap(CircuitBuildTimedOutError)
            self.count_timeout.inc()
            time_end = self.now()
            self.result_sink.send({"time_start": time_start,
                                   "time_end": time_end,
                                   "path": serialized_route,
                                   "status": "timeout"})
            return None

        def circuit_build_failure(f):
            self.count_failure.inc()
            time_end = self.now()
            self.result_sink.send({"time_start": time_start,
                                   "time_end": time_end,
                                   "path": serialized_route,
                                   "status": "failure"})
            return None

        def clean_up(opaque):
            self.tasks.pop(serialized_route)

        time_start = self.now()
        d = self.semaphore.run(build_timeout_circuit, self.state, self.clock, route, self.circuit_life_duration)
        self.tasks[serialized_route] = d
        d.addCallback(circuit_build_success)
        d.addErrback(circuit_build_timeout)
        d.addErrback(circuit_build_failure)
        d.addBoth(clean_up)

    def start_prometheus_exportor(self):
        self.count_success = Counter('circuit_build_success_counter', 'successful circuit builds')
        self.count_failure = Counter('circuit_build_failure_counter', 'failed circuit builds')
        self.count_timeout = Counter('circuit_build_timeout_counter', 'timed out circuit builds')

        if not has_prometheus_client:
            return
        root = Resource()
        root.putChild(b'metrics', MetricsResource())
        factory = Site(root)
        reactor.listenTCP(self.prometheus_port, factory, interface=self.prometheus_interface)

    def start(self):
        self.start_prometheus_exportor()

        def pop():
            try:
                route = self.circuits.next()
                log.msg(self.serialize_route(route))
                self.build_circuit(route)
            except StopIteration:
                self.stop()
            else:
                self.call_id = self.clock.callLater(self.circuit_build_duration, pop)
        self.clock.callLater(0, pop)

    def stop(self):
        try:
            self.call_id.cancel()
        except AlreadyCalled:
            pass
        dl = defer.DeferredList(self.tasks.values())
        dl.addCallback(lambda ign: self.result_sink.end_flush())
        dl.addCallback(lambda ign: self.stopped())
        return dl
