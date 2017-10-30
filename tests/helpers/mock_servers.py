# -*- coding: utf-8 -*-
import logging

from anki.sync import HttpSyncer, RemoteServer, RemoteMediaServer


class MockServerConnection(object):
    """
    Mock for HttpSyncer's con attribute, a httplib2 connection. All requests
    that would normally got to the remote server will be redirected to our
    server_app_to_test object.
    """

    def __init__(self, server_app_to_test):
        self.test_app = server_app_to_test

    def request(self, uri, method='GET', headers=None, body=None):
        if method == 'POST':
            logging.debug("Posting to URI '{}'.".format(uri))
            logging.info("Posting to URI '{}'.".format(uri))
            test_response = self.test_app.post(uri,
                                               params=body,
                                               headers=headers,
                                               status="*")

            resp = test_response.headers
            resp.update({
                "status": str(test_response.status_int)
            })
            cont = test_response.body
            return resp, cont
        else:
            raise Exception('Unexpected HttpSyncer.req() behavior.')


class MockRemoteServer(RemoteServer):
    """
    Mock for RemoteServer. All communication to our remote counterpart is
    routed to our TestApp object.
    """

    def __init__(self, hkey, server_test_app):
        # Create a custom connection object we will use to communicate with our
        # 'remote' server counterpart.
        connection = MockServerConnection(server_test_app)
        HttpSyncer.__init__(self, hkey, connection)

    def syncURL(self):  # Overrides RemoteServer.syncURL().
        return "/sync/"


class MockRemoteMediaServer(RemoteMediaServer):
    """
    Mock for RemoteMediaServer. All communication to our remote counterpart is
    routed to our TestApp object.
    """

    def __init__(self, col, hkey, server_test_app):
        # Create a custom connection object we will use to communicate with our
        # 'remote' server counterpart.
        connection = MockServerConnection(server_test_app)
        HttpSyncer.__init__(self, hkey, connection)

    def syncURL(self):  # Overrides RemoteServer.syncURL().
        return "/msync/"
