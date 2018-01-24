import sys

from twisted.internet import defer, reactor, endpoints
from txtorcon.interface import CircuitListenerMixin, IStreamAttacher, StreamListenerMixin
import txtorcon
from txtorcon import TorState, launch_tor
from txtorcon.util import available_tcp_port
from zope.interface import implementer

from bwscanner.logger import log


@implementer(IStreamAttacher)
class SOCKSClientStreamAttacher(CircuitListenerMixin, StreamListenerMixin):
    """
    An attacher that builds a chosen path for a client identified by
    its source port and ip address.
    """

    def __init__(self, state):
        """
        Instantiates a SOCKSClientStreamAttacher with a
        txtorcon.torstate.TorState instance.
        """
        self.state = state
        self.waiting_circuits = {}
        self.expected_streams = {}
        self.state.add_stream_listener(self)
        self.state.add_circuit_listener(self)

    def create_circuit(self, host, port, path, using_guards=False):
        """
        Specify the path for streams created on a specific client
        SOCKS connection.

        Returns a deferred that calls back with the constructed circuit
        or errs back with a failure instance.
        """
        circ_deferred = defer.Deferred()
        key = (str(host), int(port))
        self.expected_streams[key] = circ_deferred

        def add_to_waiting(circ):
            self.waiting_circuits[circ.id] = (circ, circ_deferred)
            return circ

        circuit_build = self.state.build_circuit(
            path, using_guards=using_guards)
        circuit_build.addCallback(add_to_waiting)
        return circ_deferred

    def attach_stream(self, stream, _):
        """
        Attaches a NEW stream to the circuit created for it by matching the
        source address and source port of the SOCKS client connection to the
        corresponding circuit in the expected_streams dictionary.

        Returns a deferred that calls back with the appropriate circuit,
        or None if there is no matching entry.

        Note, Tor can be configured to leave streams unattached by setting
        the "__LeaveStreamsUnattached" torrc option to "1".
        """
        try:
            key = (str(stream.source_addr), int(stream.source_port))
            return self.expected_streams.pop(key)
        except KeyError:
            # We didn't expect this stream, so let Tor handle it
            return None

    def circuit_built(self, circuit):
        """
        Calls back the deferred awaiting the circuit build with the
        circuit object.
        """
        if circuit.purpose != "GENERAL":
            return
        try:
            (_, circ_deferred) = self.waiting_circuits.pop(circuit.id)
            circ_deferred.callback(circuit)
        except KeyError:
            pass

    def circuit_failed(self, circuit, **kw):
        """
        Calls the errback of the deferred waiting the circuit build if the
        circuit build failed. The failure reason is contained in the circuit
        object. The corresponding state in waiting_circuits is removed.

        If the circuit failure did not correspond to a circuit requested
        by create_circuit, it is ignored.
        """
        try:
            (circ, circ_deferred) = self.waiting_circuits.pop(circuit.id)
            circ_deferred.errback(circ)
        except KeyError:
            pass


class StreamClosedListener(StreamListenerMixin):
    """
    Closes the contained circuit if the listened stream closes.

    This StreamListener is used to instruct Tor to close circuits
    immediately after a stream completes rather than wait for the
    circuit to time out.
    """
    def __init__(self, circ):
        self.circ = circ

    def stream_closed(self, *args, **kw):
        self.circ.close(ifUnused=True)


def start_tor(config):
    """
    Launches tor with random TCP ports chosen for SocksPort and ControlPort,
    and other options specified by a txtorcon.torconfig.TorConfig instance.

    Returns a deferred that calls back with a txtorcon.torstate.TorState
    instance.
    """
    def get_random_tor_ports():
        d2 = available_tcp_port(reactor)
        d2.addCallback(lambda port: config.__setattr__('SocksPort', port))
        d2.addCallback(lambda _: available_tcp_port(reactor))
        d2.addCallback(lambda port: config.__setattr__('ControlPort', port))
        return d2

    def launch_and_get_state(ignore):
        d2 = launch_tor(config, reactor, stdout=sys.stdout)
        d2.addCallback(lambda tpp: TorState(tpp.tor_protocol).post_bootstrap)
        return d2
    return get_random_tor_ports().addCallback(launch_and_get_state)


def setconf_singleport_exit(tor):
    port = available_tcp_port(reactor)

    def add_single_port_exit(port):
        tor.protocol.set_conf('PublishServerDescriptor', '0',
                              'PortForwarding', '1',
                              'AssumeReachable', '1',
                              'ClientRejectInternalAddresses', '0',
                              'OrPort', 'auto',
                              'ExitPolicyRejectPrivate', '0',
                              'ExitPolicy', 'accept 127.0.0.1:{}, reject *:*'.format(port))
    return port.addCallback(add_single_port_exit).addCallback(
        lambda ign: tor.routers[tor.protocol.get_info("fingerprint")])


@defer.inlineCallbacks
def connect_to_tor(launch_tor, circuit_build_timeout, circuit_idle_timeout, control_port=9051):
    """
    Launch or connect to a Tor instance

    Configure Tor with the passed options and return a Deferred
    """
    # Options for spawned or running Tor to load the correct descriptors.
    tor_options = {
        'LearnCircuitBuildTimeout': 0,  # Disable adaptive circuit timeouts.
        'CircuitBuildTimeout': circuit_build_timeout,
        'CircuitIdleTimeout': circuit_idle_timeout,
        'UseEntryGuards': 0,  # Disable UseEntryGuards to avoid PathBias warnings.
        'UseMicroDescriptors': 0,
        'FetchUselessDescriptors': 1,
        'FetchDirInfoEarly': 1,
        'FetchDirInfoExtraEarly': 1,
    }

    if launch_tor:
        log.info("Spawning a new Tor instance.")
        # TODO: Pass in data_dir directory so consensus can be cached
        tor = yield txtorcon.launch(reactor)
    else:
        log.info("Trying to connect to a running Tor instance.")
        tor = yield txtorcon.connect(
            reactor,
            endpoints.TCP4ClientEndpoint(reactor, "localhost", control_port)
        )

    # Get Tor state first to avoid a race conditions where CONF_CHANGED
    # messages are received while Txtorcon is reading the consensus.
    tor_state = yield tor.create_state()

    # Update Tor config options from dictionary
    tor_config = yield tor.get_config()
    for key, value in tor_options.items():
        setattr(tor_config, key, value)
    yield tor_config.save()  # Send updated options to Tor

    defer.returnValue(tor_state)
