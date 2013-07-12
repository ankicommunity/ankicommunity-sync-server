
import sys
sys.path.insert(0, "/usr/share/anki")

def server_runner(app, global_conf, **kw):
    """ Special version of paste.httpserver.server_runner which calls 
    AnkiServer.threading.shutdown() on server exit."""

    from paste.httpserver import server_runner as paste_server_runner
    from AnkiServer.threading import shutdown
    try:
        paste_server_runner(app, global_conf, **kw)
    finally:
        shutdown()

