import logging

from wsgiref.simple_server import make_server, WSGIRequestHandler

from ankisyncd.thread import shutdown

logger = logging.getLogger(__name__)


class RequestHandler(WSGIRequestHandler):
    logger = logging.getLogger("ankisyncd.http")

    def log_error(self, format, *args):
        self.logger.error("%s %s", self.address_string(), format % args)

    def log_message(self, format, *args):
        self.logger.info("%s %s", self.address_string(), format % args)


def run_server(app, host: str = None, port: int = None):
    httpd = make_server(host, port, app, handler_class=RequestHandler)

    try:
        logger.info("Serving HTTP on {} port {}...".format(*httpd.server_address))
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Exiting...")
    finally:
        shutdown()
