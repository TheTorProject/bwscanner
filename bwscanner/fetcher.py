from twisted.internet import interfaces, reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.web.client import (SchemeNotSupported, Agent, BrowserLikePolicyForHTTPS)
from txsocksx.client import SOCKS5ClientFactory
from txsocksx.tls import TLSWrapClientEndpoint
from zope.interface import implementer

# from bwscanner.logger import log


def get_tor_socks_endpoint(tor_state):
    proxy_endpoint = tor_state.protocol.get_conf("SocksPort")

    def extract_port_value(result):
        # Get the first SOCKS port number if any. SocksPort can be a single string or a list.
        # Tor now also has support for unix domain SOCKS sockets so we need to be careful to just
        # pick a SOCKS port.
        if isinstance(result['SocksPort'], list):
            port = next(port for port in result['SocksPort'] if port.isdigit())
        else:
            port = result['SocksPort']

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

        self.tor_socks_endpoint = get_tor_socks_endpoint(state)

    def connect(self, protocol_factory):
        """
        Implements L{IStreamClientEndpoint.connect} to connect via TCP, after
        SOCKS5 negotiation and Tor circuit construction is done.
        """
        proxy_factory = SOCKS5ClientFactory(self.host, self.port, protocol_factory)
        self.tor_socks_endpoint.addCallback(lambda end: end.connect(proxy_factory))

        def _create_circ(proto):
            hp = proto.transport.getHost()
            d = self.state._attacher.create_circuit(hp.host, hp.port, self.path)
            d.addErrback(proxy_factory.deferred.errback)
            return proxy_factory.deferred

        return self.tor_socks_endpoint.addCallback(_create_circ)


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
