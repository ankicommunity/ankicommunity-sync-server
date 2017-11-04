# -*- coding: utf-8 -*-
import io
import logging
import types

from anki.sync import HttpSyncer, RemoteServer, RemoteMediaServer


class MockServerConnection:
    """
    Mock for HttpSyncer's client attribute, an AnkiRequestsClient. All requests
    that would normally got to the remote server will be redirected to our
    server_app_to_test object.
    """

    def __init__(self, server_app_to_test):
        self.test_app = server_app_to_test

    def post(self, url, data, headers):
        logging.debug("Posting to URI '{}'.".format(url))
        r = self.test_app.post(url, params=data.read(), headers=headers, status="*")
        return types.SimpleNamespace(status_code=r.status_int, body=r.body)


    def streamContent(self, r):
            return r.body


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
