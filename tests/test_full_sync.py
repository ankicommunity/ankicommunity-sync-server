# -*- coding: utf-8 -*-

import os
import unittest
import configparser

from ankisyncd.full_sync import FullSyncManager, get_full_sync_manager

import helpers.server_utils

class FakeFullSyncManager(FullSyncManager):
    def __init__(self, config):
        pass

class BadFullSyncManager:
    pass

class FullSyncManagerFactoryTest(unittest.TestCase):
    def test_get_full_sync_manager(self):
        # Get absolute path to development ini file.
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ini_file_path = os.path.join(script_dir,
                                     "assets",
                                     "test.conf")

        # Create temporary files and dirs the server will use.
        server_paths = helpers.server_utils.create_server_paths()

        config = configparser.ConfigParser()
        config.read(ini_file_path)

        # Use custom files and dirs in settings. Should be PersistenceManager
        config['sync_app'].update(server_paths)
        self.assertTrue(type(get_full_sync_manager(config['sync_app']) == FullSyncManager))

        # A conf-specified FullSyncManager is loaded
        config.set("sync_app", "full_sync_manager", 'test_full_sync.FakeFullSyncManager')
        self.assertTrue(type(get_full_sync_manager(config['sync_app'])) == FakeFullSyncManager)

        # Should fail at load time if the class doesn't inherit from FullSyncManager
        config.set("sync_app", "full_sync_manager", 'test_full_sync.BadFullSyncManager')
        with self.assertRaises(TypeError):
            pm = get_full_sync_manager(config['sync_app'])

