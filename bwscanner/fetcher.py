import warnings
import hashlib

from twisted.internet import reactor, defer, protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.web.client import (ResponseDone, PotentialDataLoss, PartialDownloadError)

from bwscanner.logger import log


def fetch(tor_state, path, url):
    d = tor_state.build_circuit(path, False)
    sport = get_tor_socks_endpoint(tor_state)
    d.addCallback(lambda c: c.when_built())
    d.addCallback(lambda c: c.web_agent(reactor, sport))
    return d.addCallback(lambda a: a.request("GET", url))


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


class hashingReadBodyProtocol(protocol.Protocol):
    """
    Protocol that collects data sent to it and hashes it.

    This is a helper for L{IResponse.deliverBody}, which collects the body and
    fires a deferred with it.
    """

    def __init__(self, status, message, deferred):
        self.deferred = deferred
        self.status = status
        self.message = message
        self.hash_state = hashlib.sha1()

    def dataReceived(self, data):
        """
        Accumulate and hash some more bytes from the response.
        """
        self.hash_state.update(data)

    def connectionLost(self, reason):
        """
        Deliver the accumulated response bytes to the waiting L{Deferred}, if
        the response body has been completely received without error.

        We can cancel the readBody Deferred after it is running. Canceling
        the Deferred closes the connection. We want to check if the deferred
        was already called to avoid raising an AlreadyCalled exception.
        """
        if not self.deferred.called:
            if reason.check(ResponseDone):
                self.deferred.callback(self.hash_state.hexdigest())
            elif reason.check(PotentialDataLoss):
                self.deferred.errback(
                    PartialDownloadError(self.status, self.message,
                                         self.hash_state.hexdigest()))
            else:
                self.deferred.errback(reason)
        else:
            log.debug("Deferred already called before connectionLost on hashingReadBodyProtocol.")


def hashingReadBody(response):
    """
    Get the body of an L{IResponse} and return the SHA1 hash of the body.

    @param response: The HTTP response for which the body will be read.
    @type response: L{IResponse} provider

    @return: A L{Deferred} which will fire with the hex encoded SHA1 hash
        of the response. Cancelling it will close the connection to the
        server immediately.
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
    protocol = hashingReadBodyProtocol(response.code, response.phrase, d)

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
