from twisted.internet import defer, reactor
from twisted.web.client import readBody
from twisted.web.resource import Resource
from twisted.web.server import Site
from txtorcon.circuit import Circuit
from txtorcon.util import available_tcp_port

from bwscanner.listener import CircuitEventListener, StreamBandwidthListener
from bwscanner.fetcher import OnionRoutedAgent
from test.template import TorTestCase

import random
import time

class FakeCircuit(Circuit):
    def __init__(self, id=None, state='BOGUS'):
        self.streams = []
        self.purpose = ''
        self.path = []
        self.id = id or random.randint(2222, 7777)
        self.state = state

class TestCircuitEventListener(TorTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super(TestCircuitEventListener, self).setUp()
        self.circuit_event_listener = CircuitEventListener(self.tor)
        self.tor.add_circuit_listener(self.circuit_event_listener)

    @defer.inlineCallbacks
    def test_circuit_lifecycle(self):
        path = self.random_path()
        circ = yield self.attacher.create_circuit('127.0.0.1', 1234, path)
        self.assertIsInstance(circ, Circuit)
        self.assertEqual(circ.path, path)
        circuit_lifecycle = self.circuit_event_listener.circuits[circ]
        #XXX argh, we haven't gotten all the events from Tor yet...
        # hax to block until we've made Tor do something...
        yield circ.close(ifUnused=False)
        yield self.tor.protocol.get_info('version')
        expected_states = ['circuit_new', 'circuit_launched', 'circuit_extend',
                           'circuit_extend', 'circuit_extend', 'circuit_built',
                           'circuit_closed']
        assert len(circuit_lifecycle) == len(expected_states)
        assert [k['event'] for k in circuit_lifecycle] == expected_states

class TestStreamBandwidthListener(TorTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super(TestStreamBandwidthListener, self).setUp()
        self.fetch_size = 8*2**20 # 8MB
        self.stream_bandwidth_listener = yield StreamBandwidthListener(self.tor)

        class DummyResource(Resource):
            isLeaf = True
            def render_GET(self, request):
                return 'a'*8*2**20

        self.port = yield available_tcp_port(reactor)
        self.site = Site(DummyResource())
        self.test_service = yield reactor.listenTCP(self.port, self.site)

    @defer.inlineCallbacks
    def test_circ_bw(self):
        r = yield self.do_fetch()
        bw_events = self.stream_bandwidth_listener.circ_bw_events[r['circ']]
        assert len(bw_events) > 0
        #XXX: why are the counters reversed!?
        #assert self.fetch_size/2 <= sum([x[1] for x in bw_events]) <= self.fetch_size
        assert sum([x[1] for x in bw_events]) <= self.fetch_size
        # either this is backward, or we wrote more bytes than read?!
        assert sum([x[2] for x in bw_events]) >= sum([x[1] for x in bw_events]) 

    @defer.inlineCallbacks
    def test_stream_bw(self):
        r = yield self.do_fetch()
        bw_events = self.stream_bandwidth_listener.stream_bw_events[r['circ']]
        assert len(bw_events) > 0
        assert self.fetch_size/2 <= sum([x[1] for x in bw_events]) <= self.fetch_size

    @defer.inlineCallbacks
    def test_bw_samples(self):
        r = yield self.do_fetch()
        bw_events = self.stream_bandwidth_listener.stream_bw_events[r['circ']]
        assert len(bw_events) > 0
        assert self.fetch_size/4 <= sum([x[1] for x in bw_events]) <= self.fetch_size
        bw_samples = [x for x in self.stream_bandwidth_listener.bw_samples(r['circ'])]
        assert self.fetch_size/2 <= sum([x[0] for x in bw_samples]) <= self.fetch_size
        assert r['duration'] * .5 < sum([x[2] for x in bw_samples]) < r['duration'] * 2

    @defer.inlineCallbacks
    def test_circ_avg_bw(self):
        r = yield self.do_fetch()
        bw_events = self.stream_bandwidth_listener.stream_bw_events[r['circ']]
        #XXX: these complete too quickly to sample sufficient bytes...
        assert len(bw_events) > 0
        assert self.fetch_size/4 <= sum([x[1] for x in bw_events]) <= self.fetch_size
        circ_avg_bw = self.stream_bandwidth_listener.circ_avg_bw(r['circ'])
        assert circ_avg_bw != None
        assert circ_avg_bw['path'] == r['circ'].path
        assert self.fetch_size/4 <= circ_avg_bw['bytes_r'] <= self.fetch_size
        assert 0 < circ_avg_bw['duration'] <= r['duration']
        assert circ_avg_bw['bytes_r']/4 < circ_avg_bw['samples'] * circ_avg_bw['r_bw'] < circ_avg_bw['bytes_r']*2

    @defer.inlineCallbacks
    def do_fetch(self):
        time_start = time.time()
        path = self.random_path()
        agent = OnionRoutedAgent(reactor, path=path, state=self.tor)
        url = "http://127.0.0.1:{}".format(self.port)
        request = yield agent.request("GET", url)
        body = yield readBody(request)
        assert len(body) == self.fetch_size
        circ = [c for c in self.tor.circuits.values() if c.path == path][0]
        assert isinstance(circ, Circuit)
        defer.returnValue({'duration': time.time() - time_start, 'circ': circ})

    @defer.inlineCallbacks
    def tearDown(self):
        yield super(TestStreamBandwidthListener, self).tearDown()
        yield self.test_service.stopListening()
