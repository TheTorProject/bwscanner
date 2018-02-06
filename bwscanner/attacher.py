import txtorcon
from twisted.internet import defer, reactor, endpoints

from bwscanner.logger import log


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
        log.debug("Got NEWCONSENSUS event.")
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
        'SafeLogging': 0,
        'LogTimeGranularity': 1,
    }

    if tor_overrides:
        tor_options.update(tor_overrides)

    tor_config = txtorcon.TorConfig()

    # Update Tor config options from dictionary
    for key, value in tor_options.items():
        setattr(tor_config, key, value)

    if launch_tor:
        log.info("Spawning a new Tor instance.")
        tor = yield txtorcon.launch(reactor, data_directory=tor_dir,
                                    _tor_config=tor_config)
    else:
        log.info("Trying to connect to a running Tor instance.")
        if control_port:
            endpoint = endpoints.TCP4ClientEndpoint(reactor, "localhost", control_port)
        else:
            endpoint = None
        tor = yield txtorcon.connect(reactor, endpoint)
        # TODO: check whether CONF_CHANGED will happen here or not because
        # we get the state later
        tor.config = tor_config
        tor.config.save()

    wait_for_consensus = options_need_new_consensus(tor_config, tor_options)

    tor_state = yield tor.create_state()

    if wait_for_consensus:
        yield wait_for_newconsensus(tor_state)

    defer.returnValue(tor_state)
