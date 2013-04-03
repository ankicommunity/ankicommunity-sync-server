
def server_runner(app, global_conf, **kw):
    """ Special version of paste.httpserver.server_runner which shuts down
    the AnkiServer.deck.thread_pool on server exit. """

    from paste.httpserver import server_runner as paste_server_runner
    from AnkiServer.deck import thread_pool
    try:
        paste_server_runner(app, global_conf, **kw)
    finally:
        thread_pool.shutdown()

