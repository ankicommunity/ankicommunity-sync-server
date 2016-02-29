# -*- coding: utf-8 -*-


import os
import unittest
from webtest import TestApp


from ankisyncd.users import UserManager
from helpers.collection_utils import CollectionUtils
from helpers.db_utils import DBUtils
from helpers.file_utils import FileUtils
from helpers.mock_servers import MockRemoteServer
from helpers.monkey_patches import monkeypatch_db, unpatch_db
from helpers.server_utils import ServerUtils


class SyncAppFunctionalTestBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fileutils = FileUtils()
        cls.colutils = CollectionUtils()
        cls.serverutils = ServerUtils()
        cls.dbutils = DBUtils()

    @classmethod
    def tearDownClass(cls):
        cls.fileutils.clean_up()
        cls.fileutils = None

        cls.colutils.clean_up()
        cls.colutils = None

        cls.serverutils.clean_up()
        cls.serverutils = None

        cls.dbutils.clean_up()
        cls.dbutils = None

    def setUp(self):
        monkeypatch_db()

        # Create temporary files and dirs the server will use.
        self.server_paths = self.serverutils.create_server_paths()

        # Add a test user to the temp auth db the server will use.
        self.user_manager = UserManager(self.server_paths['auth_db'],
                                        self.server_paths['data_root'])
        self.user_manager.add_user('testuser', 'testpassword')

        # Get absolute path to development ini file.
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ini_file_path = os.path.join(script_dir,
                                     "assets",
                                     "test.conf")

        # Create SyncApp instance using the dev ini file and the temporary
        # paths.
        self.server_app = self.serverutils.create_sync_app(self.server_paths,
                                                           ini_file_path)

        # Wrap the SyncApp object in TestApp instance for testing.
        self.server_test_app = TestApp(self.server_app)

        # MockRemoteServer instance needed for testing normal collection
        # syncing and for retrieving hkey for other tests.
        self.mock_remote_server = MockRemoteServer(hkey=None,
                                                   server_test_app=self.server_test_app)

    def tearDown(self):
        self.server_paths = {}
        self.user_manager = None

        # Shut down server.
        self.server_app.collection_manager.shutdown()
        self.server_app = None

        self.client_server_connection = None

        unpatch_db()
