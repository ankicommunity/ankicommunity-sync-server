# -*- coding: utf-8 -*-
from sync_app_functional_test_base import SyncAppFunctionalTestBase


class SyncAppFunctionalHostKeyTest(SyncAppFunctionalTestBase):
    def setUp(self):
        SyncAppFunctionalTestBase.setUp(self)
        self.server = self.mock_remote_server

    def tearDown(self):
        self.server = None
        SyncAppFunctionalTestBase.tearDown(self)

    # First breakage: c7d7ff3e858415ec12785579882a4c7586cbfce4
    def test_login(self):
        self.assertIsNotNone(self.server.hostKey("testuser", "testpassword"))
        self.assertIsNone(self.server.hostKey("testuser", "wrongpassword"))
        self.assertIsNone(self.server.hostKey("wronguser", "wrongpassword"))
        self.assertIsNone(self.server.hostKey("wronguser", "testpassword"))

