from txtorcon import CircuitListenerMixin, StreamListenerMixin
import time


class CircuitEventListener(CircuitListenerMixin, StreamListenerMixin):
    def __init__(self, state, result_sink=None):
        self.state = state
        self.circuits = dict()
        self.result_sink = result_sink

    def circuit_new(self, circuit):
        circuit_new_event = dict(event='circuit_new', time=time.time(),
                                 circuit=str(circuit))
        self.circuits[circuit] = [circuit_new_event]

    def circuit_launched(self, circuit):
        try:
            circuit_launched_event = dict(event='circuit_launched', time=time.time(),
                                          circuit=str(circuit))
            self.circuits[circuit].append(circuit_launched_event)
        except KeyError:
            pass

    def circuit_extend(self, circuit, router):
        try:
            circuit_extend_event = dict(event='circuit_extend', time=time.time(),
                                        circuit=str(circuit), router=str(router))
            self.circuits[circuit].append(circuit_extend_event)
        except KeyError:
            pass

    def circuit_built(self, circuit):
        try:
            circuit_built_event = dict(event='circuit_built', time=time.time(),
                                       circuit=str(circuit))
            self.circuits[circuit].append(circuit_built_event)
        except KeyError:
            pass

    def circuit_closed(self, circuit, **kw):
        try:
            circuit_closed_event = dict(event='circuit_closed', time=time.time(),
                                        circuit=str(circuit), **kw)
            self.circuits[circuit].append(circuit_closed_event)
            if self.result_sink:
                self.result_sink.send(self.circuits.pop(circuit))
        except KeyError:
            pass

    def circuit_failed(self, circuit, **kw):
        try:
            circuit_failed_event = dict(event='circuit_failed', time=time.time(),
                                        circuit=str(circuit), **kw)
            self.circuits[circuit].append(circuit_failed_event)
            if self.result_sink:
                self.result_sink.send(self.circuits.pop(circuit))
        except KeyError:
            pass
