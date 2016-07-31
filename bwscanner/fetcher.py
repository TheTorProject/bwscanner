import warnings

from twisted.internet import interfaces, reactor, defer
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.web.client import (SchemeNotSupported, Agent, BrowserLikePolicyForHTTPS,
                                _ReadBodyProtocol, ResponseDone, PotentialDataLoss,
                                PartialDownloadError)
from txsocksx.client import SOCKS5ClientFactory
from txsocksx.tls import TLSWrapClientEndpoint
from zope.interface import implementer


def get_orport_endpoint(tor_state):
    proxy_endpoint = tor_state.protocol.get_conf("SocksPort")

    def extract_port_value(result):
        port = result['SocksPort'].split()[0]
        return int(port) if port != 'DEFAULT' else 9050
    proxy_endpoint.addCallback(extract_port_value)
    proxy_endpoint.addCallback(
        lambda port: TCP4ClientEndpoint(reactor, '127.0.0.1', port))
    return proxy_endpoint


@implementer(interfaces.IStreamClientEndpoint)
class OnionRoutedTCPClientEndpoint(object):
    def __init__(self, host, port, state, path):
        """
        @param reactor: An L{IReactorTCP} provider

        @param host: A hostname, used when connecting
        @type host: str

        @param port: The port number, used when connecting
        @type port: int

        @param path: A list of relay identities.
        @type path: list

        This endpoint will be routed through Tor over a circuit
        defined by path.
        """
        self.host = host
        self.port = port
        self.path = path
        self.state = state

        self.or_endpoint = get_orport_endpoint(state)

    def connect(self, protocol_factory):
        """
        Implements L{IStreamClientEndpoint.connect} to connect via TCP, after
        SOCKS5 negotiation and Tor circuit construction is done.
        """
        proxy_factory = SOCKS5ClientFactory(self.host, self.port, protocol_factory)
        self.or_endpoint.addCallback(lambda end: end.connect(proxy_factory))

        def _create_circ(proto):
            hp = proto.transport.getHost()
            d = self.state.attacher.create_circuit(hp.host, hp.port, self.path)
            d.addErrback(proxy_factory.deferred.errback)
            return proxy_factory.deferred

        return self.or_endpoint.addCallback(_create_circ)


class OnionRoutedAgent(Agent):
    _tlsWrapper = TLSWrapClientEndpoint
    _policyForHTTPS = BrowserLikePolicyForHTTPS

    def __init__(self, *args, **kw):
        self.path = kw.pop('path')
        self.state = kw.pop('state')
        super(OnionRoutedAgent, self).__init__(*args, **kw)

    def _getEndpoint(self, parsedURI, host=None, port=None):
        try:
            host, port = parsedURI.host, parsedURI.port
            scheme = parsedURI.scheme
        except AttributeError:
            scheme = parsedURI
        if scheme not in ('http', 'https'):
            raise SchemeNotSupported('unsupported scheme', scheme)
        endpoint = OnionRoutedTCPClientEndpoint(host, port, self.state,
                                                self.path)
        if scheme == 'https':
            if hasattr(self, '_wrapContextFactory'):
                tls_policy = self._wrapContextFactory(host, port)
            elif hasattr(self, '_policyForHTTPS'):
                tls_policy = self._policyForHTTPS().creatorForNetloc(host, port)
            else:
                raise NotImplementedError("Cannot create a TLS validation policy.")
            endpoint = self._tlsWrapper(tls_policy, endpoint)
        return endpoint


class cancelableReadBodyProtocol(_ReadBodyProtocol):
    def connectionLost(self, reason):
        """
        Deliver the accumulated response bytes to the waiting L{Deferred}, if
        the response body has been completely received without error.

        We can cancel the readBody Deferred after it is running. Canceling
        the Deferred closes the connection. We want to check if the deferred
        was already called to avoid raising an AlreadyCalled exception.
        """
        if reason.check(ResponseDone):
            self.deferred.callback(b''.join(self.dataBuffer))
        elif reason.check(PotentialDataLoss):
            self.deferred.errback(
                PartialDownloadError(self.status, self.message,
                                     b''.join(self.dataBuffer)))
        elif not self.deferred.called:
            self.deferred.errback(reason)

def cancelableReadBody(response):
    """
    Get the body of an L{IResponse} and return it as a byte string.

    This is a helper function for clients that don't want to incrementally
    receive the body of an HTTP response.

    @param response: The HTTP response for which the body will be read.
    @type response: L{IResponse} provider

    @return: A L{Deferred} which will fire with the body of the response.
        Cancelling it will close the connection to the server immediately.
    """
    def cancel(deferred):
        """
        Cancel a L{readBody} call, close the connection to the HTTP server
        immediately, if it is still open.

        @param deferred: The cancelled L{defer.Deferred}.
        """
        abort = getAbort()
        if abort is not None:
            abort()

    d = defer.Deferred(cancel)
    protocol = cancelableReadBodyProtocol(response.code, response.phrase, d)
    def getAbort():
        return getattr(protocol.transport, 'abortConnection', None)

    response.deliverBody(protocol)

    if protocol.transport is not None and getAbort() is None:
        warnings.warn(
            'Using readBody with a transport that does not have an '
            'abortConnection method',
            category=DeprecationWarning,
            stacklevel=2)

    return d
