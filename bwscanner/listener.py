from txtorcon import CircuitListenerMixin, StreamListenerMixin
from bwscanner.writer import ResultSink
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
            circuit_launched_event = dict(event='circuit_launched',
                time=time.time(), circuit=str(circuit))
            self.circuits[circuit].append(circuit_launched_event)
        except KeyError:
            pass

    def circuit_extend(self, circuit, router):
        try:
            circuit_extend_event = dict(event='circuit_extend',
                time=time.time(), circuit=str(circuit), router=str(router))
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
            circuit_closed_event = dict(event='circuit_closed',
                time=time.time(), circuit=str(circuit), **kw)
            self.circuits[circuit].append(circuit_closed_event)
            if self.result_sink:
                self.result_sink.send(self.circuits.pop(circuit))
        except KeyError:
            pass

    def circuit_failed(self, circuit, **kw):
        try:
            circuit_failed_event = dict(event='circuit_failed',
                time=time.time(), circuit=str(circuit), **kw)
            self.circuits[circuit].append(circuit_failed_event)
            if self.result_sink:
                self.result_sink.send(self.circuits.pop(circuit))
        except KeyError:
            pass

class StreamBandwidthListener(CircuitListenerMixin, StreamListenerMixin):
    def __init__(self, state):
        self.state = state
        self.stream_bw_events = dict()
        self.circ_bw_events = dict()
        self.state.protocol.add_event_listener('STREAM_BW', self.stream_bw)
        self.state.protocol.add_event_listener('CIRC_BW', self.circ_bw)

    def circ_bw(self, event):
        event = dict([x.split('=') for x in event.split()])
        now = time.time()
        circid, bytes_wrote, bytes_read = int(event['ID']), int(event['WRITTEN']), int(event['READ'])

        try:
            circuit = self.state.circuits[circid]
        except KeyError:
            return
        bw_event = now, bytes_read, bytes_wrote
        try:
            self.circ_bw_events[circuit].append(bw_event)
        except KeyError:
            self.circ_bw_events[circuit] = [bw_event]

    def stream_bw(self, event):
        now = time.time()
        streamid, bytes_wrote, bytes_read = [int(x) for x in event.split()]
        try:
            circuit = self.state.streams[streamid].circuit
        except (KeyError, AttributeError):
            return
        if not circuit: return
        bw_event = now, bytes_read, bytes_wrote
        try:
            self.stream_bw_events[circuit].append(bw_event)
        except KeyError:
            self.stream_bw_events[circuit] = [bw_event]

    def bw_samples(self, circuit):
        bws = self.stream_bw_events[circuit][:]
        t_prev, r_prev, w_prev = bws.pop(0)
        while bws:
            t_next, r_next, w_next = bws.pop(0)
            duration = t_next - t_prev
            yield r_prev, w_prev, duration
            t_prev = t_next
            r_prev = r_next
            w_prev = w_next

    def circ_avg_bw(self, circuit):
        bytes_r_total = 1
        bytes_w_total = 1
        r_avg = 0
        w_avg = 0
        n_samples = 0
        duration = 0
        if circuit not in self.stream_bw_events:
            return None

        for r, w, d in self.bw_samples(circuit):
            #r and w are in units of bytes/second
            # d is units of second
            r_avg += (r**2)/d
            w_avg += (w**2)/d
            n_samples += 1
            bytes_r_total += r
            bytes_w_total += w
            duration += d

        if n_samples > 1:
            wf = n_samples*bytes_r_total
            return {'path': circuit.path,
                    'r_bw': int(r_avg/wf),
                    'w_bw': int(w_avg/wf),
                    'duration': duration,
                    'samples': n_samples,
                    'bytes_r': bytes_r_total,
                    'bytes_w': bytes_w_total}
        else:
            return None
