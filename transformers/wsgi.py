# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2010 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Utility methods for working with WSGI servers."""

from __future__ import print_function

import errno
import os
import socket
import ssl
import sys
import time

import eventlet
import eventlet.wsgi
import greenlet
from oslo_config import cfg
from oslo_utils import excutils
from oslo_utils import netutils
from paste import deploy
import routes.middleware
import webob.dec
import webob.exc

from transformers.common import log as logging
from transformers.common import log as loggers

from transformers import exception
from transformers.i18n import _, _LE, _LI
from transformers import utils


socket_opts = [
    cfg.BoolOpt('tcp_keepalive',
                default=True,
                help="Sets the value of TCP_KEEPALIVE (True/False) for each "
                     "server socket."),
    cfg.IntOpt('tcp_keepidle',
               default=600,
               help="Sets the value of TCP_KEEPIDLE in seconds for each "
                    "server socket. Not supported on OS X."),
    cfg.IntOpt('tcp_keepalive_interval',
               help="Sets the value of TCP_KEEPINTVL in seconds for each "
                    "server socket. Not supported on OS X."),
    cfg.IntOpt('tcp_keepalive_count',
               help="Sets the value of TCP_KEEPCNT for each "
                    "server socket. Not supported on OS X."),
    cfg.StrOpt('ssl_ca_file',
               default=None,
               help="CA certificate file to use to verify "
                    "connecting clients"),
    cfg.StrOpt('ssl_cert_file',
               default=None,
               help="Certificate file to use when starting "
                    "the server securely"),
    cfg.StrOpt('ssl_key_file',
               default=None,
               help="Private key file to use when starting "
                    "the server securely"),
]

eventlet_opts = [
    cfg.IntOpt('max_header_line',
               default=16384,
               help="Maximum line size of message headers to be accepted. "
                    "max_header_line may need to be increased when using "
                    "large tokens (typically those generated by the "
                    "Keystone v3 API with big service catalogs)."),
    cfg.IntOpt('client_socket_timeout', default=900,
               help="Timeout for client connections\' socket operations. "
                    "If an incoming connection is idle for this number of "
                    "seconds it will be closed. A value of \'0\' means "
                    "wait forever."),
    cfg.BoolOpt('wsgi_keep_alive',
                default=True,
                help='If False, closes the client socket connection '
                     'explicitly. Setting it to True to maintain backward '
                     'compatibility. Recommended setting is set it to False.'),
]

CONF = cfg.CONF
CONF.register_opts(socket_opts)
CONF.register_opts(eventlet_opts)

LOG = logging.getLogger(__name__)


class Server(object):
    """Server class to manage a WSGI server, serving a WSGI application."""

    default_pool_size = 1000

    def __init__(self, name, app, host=None, port=None, pool_size=None,
                 protocol=eventlet.wsgi.HttpProtocol, backlog=128):
        """Initialize, but do not start, a WSGI server.

        :param name: Pretty name for logging.
        :param app: The WSGI application to serve.
        :param host: IP address to serve the application.
        :param port: Port number to server the application.
        :param pool_size: Maximum number of eventlets to spawn concurrently.
        :returns: None

        """
        # Allow operators to customize http requests max header line size.
        eventlet.wsgi.MAX_HEADER_LINE = CONF.max_header_line
        self.client_socket_timeout = CONF.client_socket_timeout or None
        self.name = name
        self.app = app
        self._host = host or "0.0.0.0"
        self._port = port or 0
        self._server = None
        self._socket = None
        self._protocol = protocol
        self.pool_size = pool_size or self.default_pool_size
        self._pool = eventlet.GreenPool(self.pool_size)
        self._logger = logging.getLogger("eventlet.wsgi.server")
        self._wsgi_logger = loggers.WritableLogger(self._logger)

        if backlog < 1:
            raise exception.InvalidInput(
                reason='The backlog must be more than 1')

        bind_addr = (host, port)
        # TODO(dims): eventlet's green dns/socket module does not actually
        # support IPv6 in getaddrinfo(). We need to get around this in the
        # future or monitor upstream for a fix
        try:
            info = socket.getaddrinfo(bind_addr[0],
                                      bind_addr[1],
                                      socket.AF_UNSPEC,
                                      socket.SOCK_STREAM)[0]
            family = info[0]
            bind_addr = info[-1]
        except Exception:
            family = socket.AF_INET

        cert_file = CONF.ssl_cert_file
        key_file = CONF.ssl_key_file
        ca_file = CONF.ssl_ca_file
        self._use_ssl = cert_file or key_file

        if cert_file and not os.path.exists(cert_file):
            raise RuntimeError(_("Unable to find cert_file : %s")
                               % cert_file)

        if ca_file and not os.path.exists(ca_file):
            raise RuntimeError(_("Unable to find ca_file : %s") % ca_file)

        if key_file and not os.path.exists(key_file):
            raise RuntimeError(_("Unable to find key_file : %s")
                               % key_file)

        if self._use_ssl and (not cert_file or not key_file):
            raise RuntimeError(_("When running server in SSL mode, you "
                                 "must specify both a cert_file and "
                                 "key_file option value in your "
                                 "configuration file."))

        retry_until = time.time() + 30
        while not self._socket and time.time() < retry_until:
            try:
                self._socket = eventlet.listen(bind_addr, backlog=backlog,
                                               family=family)
            except socket.error as err:
                if err.args[0] != errno.EADDRINUSE:
                    raise
                eventlet.sleep(0.1)

        if not self._socket:
            raise RuntimeError(_("Could not bind to %(host)s:%(port)s "
                               "after trying for 30 seconds") %
                               {'host': host, 'port': port})

        (self._host, self._port) = self._socket.getsockname()[0:2]
        LOG.info(_LI("%(name)s listening on %(_host)s:%(_port)s"),
                 {'name': self.name, '_host': self._host, '_port': self._port})

    def start(self):
        """Start serving a WSGI application.

        :returns: None
        :raises: cinder.exception.InvalidInput

        """
        # The server socket object will be closed after server exits,
        # but the underlying file descriptor will remain open, and will
        # give bad file descriptor error. So duplicating the socket object,
        # to keep file descriptor usable.

        dup_socket = self._socket.dup()
        dup_socket.setsockopt(socket.SOL_SOCKET,
                              socket.SO_REUSEADDR, 1)

        # NOTE(praneshp): Call set_tcp_keepalive in oslo to set
        # tcp keepalive parameters. Sockets can hang around forever
        # without keepalive
        netutils.set_tcp_keepalive(dup_socket,
                                   CONF.tcp_keepalive,
                                   CONF.tcp_keepidle,
                                   CONF.tcp_keepalive_count,
                                   CONF.tcp_keepalive_interval)

        if self._use_ssl:
            try:
                ssl_kwargs = {
                    'server_side': True,
                    'certfile': CONF.ssl_cert_file,
                    'keyfile': CONF.ssl_key_file,
                    'cert_reqs': ssl.CERT_NONE,
                }

                if CONF.ssl_ca_file:
                    ssl_kwargs['ca_certs'] = CONF.ssl_ca_file
                    ssl_kwargs['cert_reqs'] = ssl.CERT_REQUIRED

                dup_socket = ssl.wrap_socket(dup_socket,
                                             **ssl_kwargs)
            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.error(_LE("Failed to start %(name)s on %(_host)s:"
                                  "%(_port)s with SSL "
                                  "support."), self.__dict__)

        wsgi_kwargs = {
            'func': eventlet.wsgi.server,
            'sock': dup_socket,
            'site': self.app,
            'protocol': self._protocol,
            'custom_pool': self._pool,
            'log': self._wsgi_logger,
            'socket_timeout': self.client_socket_timeout,
            'keepalive': CONF.wsgi_keep_alive
        }

        self._server = eventlet.spawn(**wsgi_kwargs)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def stop(self):
        """Stop this server.

        This is not a very nice action, as currently the method by which a
        server is stopped is by killing its eventlet.

        :returns: None

        """
        LOG.info(_LI("Stopping WSGI server."))
        if self._server is not None:
            # Resize pool to stop new requests from being processed
            self._pool.resize(0)
            self._server.kill()

    def wait(self):
        """Block, until the server has stopped.

        Waits on the server's eventlet to finish, then returns.

        :returns: None

        """
        try:
            if self._server is not None:
                self._pool.waitall()
                self._server.wait()
        except greenlet.GreenletExit:
            LOG.info(_LI("WSGI server has stopped."))

    def reset(self):
        """Reset server greenpool size to default.

        :returns: None

        """
        self._pool.resize(self.pool_size)


class Request(webob.Request):
    pass


class Application(object):
    """Base WSGI application wrapper. Subclasses need to implement __call__."""

    @classmethod
    def factory(cls, global_config, **local_config):
        """Used for paste app factories in paste.deploy config files.

        Any local configuration (that is, values under the [app:APPNAME]
        section of the paste config) will be passed into the `__init__` method
        as kwargs.

        A hypothetical configuration would look like:

            [app:wadl]
            latest_version = 1.3
            paste.app_factory = cinder.api.fancy_api:Wadl.factory

        which would result in a call to the `Wadl` class as

            import cinder.api.fancy_api
            fancy_api.Wadl(latest_version='1.3')

        You could of course re-implement the `factory` method in subclasses,
        but using the kwarg passing it shouldn't be necessary.

        """
        return cls(**local_config)

    def __call__(self, environ, start_response):
        r"""Subclasses will probably want to implement __call__ like this:

        @webob.dec.wsgify(RequestClass=Request)
        def __call__(self, req):
          # Any of the following objects work as responses:

          # Option 1: simple string
          res = 'message\n'

          # Option 2: a nicely formatted HTTP exception page
          res = exc.HTTPForbidden(explanation='Nice try')

          # Option 3: a webob Response object (in case you need to play with
          # headers, or you want to be treated like an iterable)
          res = Response();
          res.app_iter = open('somefile')

          # Option 4: any wsgi app to be run next
          res = self.application

          # Option 5: you can get a Response object for a wsgi app, too, to
          # play with headers etc
          res = req.get_response(self.application)

          # You can then just return your response...
          return res
          # ... or set req.response and return None.
          req.response = res

        See the end of http://pythonpaste.org/webob/modules/dec.html
        for more info.

        """
        raise NotImplementedError(_('You must implement __call__'))


class Middleware(Application):
    """Base WSGI middleware.

    These classes require an application to be
    initialized that will be called next.  By default the middleware will
    simply call its wrapped app, or you can override __call__ to customize its
    behavior.

    """

    @classmethod
    def factory(cls, global_config, **local_config):
        """Used for paste app factories in paste.deploy config files.

        Any local configuration (that is, values under the [filter:APPNAME]
        section of the paste config) will be passed into the `__init__` method
        as kwargs.

        A hypothetical configuration would look like:

            [filter:analytics]
            redis_host = 127.0.0.1
            paste.filter_factory = cinder.api.analytics:Analytics.factory

        which would result in a call to the `Analytics` class as

            import cinder.api.analytics
            analytics.Analytics(app_from_paste, redis_host='127.0.0.1')

        You could of course re-implement the `factory` method in subclasses,
        but using the kwarg passing it shouldn't be necessary.

        """
        def _factory(app):
            return cls(app, **local_config)
        return _factory

    def __init__(self, application):
        self.application = application

    def process_request(self, req):
        """Called on each request.

        If this returns None, the next application down the stack will be
        executed. If it returns a response then that response will be returned
        and execution will stop here.

        """
        return None

    def process_response(self, response):
        """Do whatever you'd like to the response."""
        return response

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        response = self.process_request(req)
        if response:
            return response
        response = req.get_response(self.application)
        return self.process_response(response)


class Debug(Middleware):
    """Helper class for debugging a WSGI application.

    Can be inserted into any WSGI application chain to get information
    about the request and response.

    """

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        print(('*' * 40) + ' REQUEST ENVIRON')  # noqa
        for key, value in req.environ.items():
            print(key, '=', value)  # noqa
        print()  # noqa
        resp = req.get_response(self.application)

        print(('*' * 40) + ' RESPONSE HEADERS')  # noqa
        for (key, value) in resp.headers.iteritems():
            print(key, '=', value)  # noqa
        print()  # noqa

        resp.app_iter = self.print_generator(resp.app_iter)

        return resp

    @staticmethod
    def print_generator(app_iter):
        """Iterator that prints the contents of a wrapper string."""
        print(('*' * 40) + ' BODY')  # noqa
        for part in app_iter:
            sys.stdout.write(part)
            sys.stdout.flush()
            yield part
        print()  # noqa


class Router(object):
    """WSGI middleware that maps incoming requests to WSGI apps."""

    def __init__(self, mapper):
        """Create a router for the given routes.Mapper.

        Each route in `mapper` must specify a 'controller', which is a
        WSGI app to call.  You'll probably want to specify an 'action' as
        well and have your controller be an object that can route
        the request to the action-specific method.

        Examples:
          mapper = routes.Mapper()
          sc = ServerController()

          # Explicit mapping of one route to a controller+action
          mapper.connect(None, '/svrlist', controller=sc, action='list')

          # Actions are all implicitly defined
          mapper.resource('server', 'servers', controller=sc)

          # Pointing to an arbitrary WSGI app.  You can specify the
          # {path_info:.*} parameter so the target app can be handed just that
          # section of the URL.
          mapper.connect(None, '/v1.0/{path_info:.*}', controller=BlogApp())

        """
        self.map = mapper
        self._router = routes.middleware.RoutesMiddleware(self._dispatch,
                                                          self.map)

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        """Route the incoming request to a controller based on self.map.

        If no match, return a 404.

        """
        return self._router

    @staticmethod
    @webob.dec.wsgify(RequestClass=Request)
    def _dispatch(req):
        """Dispatch the request to the appropriate controller.

        Called by self._router after matching the incoming request to a route
        and putting the information into req.environ.  Either returns 404
        or the routed WSGI app's response.

        """
        match = req.environ['wsgiorg.routing_args'][1]
        if not match:
            return webob.exc.HTTPNotFound()
        app = match['controller']
        return app


class Loader(object):
    """Used to load WSGI applications from paste configurations."""

    def __init__(self, config_path=None):
        """Initialize the loader, and attempt to find the config.

        :param config_path: Full or relative path to the paste config.
        :returns: None

        """
        config_path = config_path or CONF.api_paste_config
        self.config_path = utils.find_config(config_path)

    def load_app(self, name):
        """Return the paste URLMap wrapped WSGI application.

        :param name: Name of the application to load.
        :returns: Paste URLMap object wrapping the requested application.
        :raises: `cinder.exception.PasteAppNotFound`

        """
        try:
            return deploy.loadapp("config:%s" % self.config_path, name=name)
        except LookupError:
            LOG.exception(_LE("Error loading app %s"), name)
            raise exception.PasteAppNotFound(name=name, path=self.config_path)
