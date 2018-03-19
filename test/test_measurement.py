from twisted.internet import defer, reactor
from twisted.web.resource import Resource
from twisted.web.server import Site
from txtorcon.util import available_tcp_port
from bwscanner.measurement import BwScan
from test.template import TorTestCase
from tempfile import mkdtemp

import os
import json
from shutil import rmtree


class TestBwscan(TorTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super(TestBwscan, self).setUp()

        # Remove test harness attacher as another attacher is added in BwScan()
        self.tor_state.set_attacher(None, reactor)

        class DummyResource(Resource):
            isLeaf = True

            def render_GET(self, request):
                size = request.uri.split('/')[-1]
                if 'k' in size:
                    size = int(size[:-1]) * (2**10)
                elif 'M' in size:
                    size = int(size[:-1]) * (2**20)
                return 'a' * size

        self.port = yield available_tcp_port(reactor)
        self.test_service = yield reactor.listenTCP(
            self.port, Site(DummyResource()))

    def test_scan_chutney(self):
        # check that each run is producing the same input set!
        self.tmp = mkdtemp()
        scan = BwScan(self.tor_state, reactor, self.tmp)
        scan.baseurl = 'http://127.0.0.1:{}'.format(self.port)

        def check_all_routers_measured(measurement_dir):
            """
            Load the measurement files from the tmp directory and confirm
            we a measurements for every relay.
            """
            measurements = []
            measured_relays = set()
            all_relays = set([r.id_hex for r in self.routers])

            for filename in os.listdir(measurement_dir):
                result_path = os.path.join(measurement_dir, filename)
                with open(result_path, 'r') as result_file:
                    measurements.extend(json.load(result_file))

            for measurement in measurements:
                measured_relays.update({str(router)
                                        for router in measurement['path']})

            failed_measurements = [measurement for measurement in measurements
                                   if 'failure' in measurement]

            # check that every router has been measured at least once
            assert measured_relays == all_relays
            assert not failed_measurements

        scan = scan.run_scan()
        scan.addCallback(lambda _: check_all_routers_measured(self.tmp))
        return scan

    @defer.inlineCallbacks
    def tearDown(self):
        yield super(TestBwscan, self).tearDown()
        yield self.test_service.stopListening()
        rmtree(self.tmp)
