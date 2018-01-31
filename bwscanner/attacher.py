import txtorcon
from twisted.internet import defer, reactor, endpoints
from txtorcon.interface import CircuitListenerMixin, IStreamAttacher, StreamListenerMixin
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


def options_need_new_consensus(tor_config, new_options):
    """
    Check if we need to wait for a new consensus after updating
    the Tor config with the new options.
    """
    if "UseMicroDescriptors" in new_options:
        if tor_config.UseMicroDescriptors != new_options["UseMicroDescriptors"]:
            log.debug("Changing UseMicroDescriptors from {current} to {new}.",
                      current=tor_config.UseMicroDescriptors,
                      new=new_options["UseMicroDescriptors"])
            return True
    return False


def wait_for_newconsensus(tor_state):
    got_consensus = defer.Deferred()

    def got_newconsensus(event):
        log.debug("Got NEWCONSENSUS event: {event}", event=event)
        got_consensus.callback(event)
        tor_state.protocol.remove_event_listener('NEWCONSENSUS', got_newconsensus)

    tor_state.protocol.add_event_listener('NEWCONSENSUS', got_newconsensus)
    return got_consensus


@defer.inlineCallbacks
def connect_to_tor(launch_tor, circuit_build_timeout, tor_dir=None, control_port=None,
                   tor_overrides=None):
    """
    Launch or connect to a Tor instance

    Configure Tor with the passed options and return a Deferred
    """
    # Options for spawned or running Tor to load the correct descriptors.
    tor_options = {
        'LearnCircuitBuildTimeout': 0,  # Disable adaptive circuit timeouts.
        'CircuitBuildTimeout': circuit_build_timeout,
        'UseEntryGuards': 0,  # Disable UseEntryGuards to avoid PathBias warnings.
        'UseMicroDescriptors': 0,
        'FetchUselessDescriptors': 1,
        'FetchDirInfoEarly': 1,
        'FetchDirInfoExtraEarly': 1,
    }

    if tor_overrides:
        tor_options.update(tor_overrides)

    if launch_tor:
        log.info("Spawning a new Tor instance.")
        tor = yield txtorcon.launch(reactor, data_directory=tor_dir)
    else:
        log.info("Trying to connect to a running Tor instance.")
        if control_port:
            endpoint = endpoints.TCP4ClientEndpoint(reactor, "localhost", control_port)
        else:
            endpoint = None
        tor = yield txtorcon.connect(reactor, endpoint)

    # Get Tor state first to avoid a race conditions where CONF_CHANGED
    # messages are received while Txtorcon is reading the consensus.
    tor_state = yield tor.create_state()

    # Get current TorConfig object
    tor_config = yield tor.get_config()
    wait_for_consensus = options_need_new_consensus(tor_config, tor_options)

    # Update Tor config options from dictionary
    for key, value in tor_options.items():
        setattr(tor_config, key, value)
    yield tor_config.save()  # Send updated options to Tor

    if wait_for_consensus:
        yield wait_for_newconsensus(tor_state)

    defer.returnValue(tor_state)
