# -*- coding: utf-8 -*-

import os
import tempfile
import sqlite3
import unittest
import configparser

from ankisyncd.sessions import SimpleSessionManager
from ankisyncd.sessions import SqliteSessionManager
from ankisyncd.sessions import get_session_manager

from ankisyncd.sync_app import SyncUserSession

import helpers.server_utils

class FakeSessionManager(SimpleSessionManager):
    def __init__(self, config):
        pass

class BadSessionManager:
    pass

class SessionManagerFactoryTest(unittest.TestCase):
    def test_get_session_manager(self):
        # Get absolute path to development ini file.
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ini_file_path = os.path.join(script_dir,
                                     "assets",
                                     "test.conf")

        # Create temporary files and dirs the server will use.
        server_paths = helpers.server_utils.create_server_paths()

        config = configparser.ConfigParser()
        config.read(ini_file_path)

        # Use custom files and dirs in settings. Should be SqliteSessionManager
        config['sync_app'].update(server_paths)
        self.assertTrue(type(get_session_manager(config['sync_app']) == SqliteSessionManager))

        # No value defaults to SimpleSessionManager
        config.remove_option("sync_app", "session_db_path")
        self.assertTrue(type(get_session_manager(config['sync_app'])) == SimpleSessionManager)

        # A conf-specified SessionManager is loaded
        config.set("sync_app", "session_manager", 'test_sessions.FakeSessionManager')
        self.assertTrue(type(get_session_manager(config['sync_app'])) == FakeSessionManager)

        # Should fail at load time if the class doesn't inherit from  SimpleSessionManager
        config.set("sync_app", "session_manager", 'test_sessions.BadSessionManager')
        with self.assertRaises(TypeError):
            sm = get_session_manager(config['sync_app'])

        # Add the session_db_path back, it should take precedence over BadSessionManager
        config['sync_app'].update(server_paths)
        self.assertTrue(type(get_session_manager(config['sync_app'])) == SqliteSessionManager)


class SimpleSessionManagerTest(unittest.TestCase):
    test_hkey = '1234567890'
    sdir = tempfile.mkdtemp(suffix="_session")
    os.rmdir(sdir)
    test_session = SyncUserSession('testName', sdir, None, None)

    def setUp(self):
        self.sessionManager = SimpleSessionManager()

    def tearDown(self):
        self.sessionManager = None

    def test_save(self):
        self.sessionManager.save(self.test_hkey, self.test_session)
        self.assertEqual(self.sessionManager.sessions[self.test_hkey].name,
                         self.test_session.name)
        self.assertEqual(self.sessionManager.sessions[self.test_hkey].path,
                         self.test_session.path)

    def test_delete(self):
        self.sessionManager.save(self.test_hkey, self.test_session)
        self.assertTrue(self.test_hkey in self.sessionManager.sessions)

        self.sessionManager.delete(self.test_hkey)

        self.assertTrue(self.test_hkey not in self.sessionManager.sessions)

    def test_load(self):
        self.sessionManager.save(self.test_hkey, self.test_session)
        self.assertTrue(self.test_hkey in self.sessionManager.sessions)

        loaded_session = self.sessionManager.load(self.test_hkey)
        self.assertEqual(loaded_session.name, self.test_session.name)
        self.assertEqual(loaded_session.path, self.test_session.path)


class SqliteSessionManagerTest(SimpleSessionManagerTest):
    file_descriptor, _test_sess_db_path = tempfile.mkstemp(suffix=".db")
    os.close(file_descriptor)
    os.unlink(_test_sess_db_path)

    def setUp(self):
        self.sessionManager = SqliteSessionManager(self._test_sess_db_path)

    def tearDown(self):
        if os.path.exists(self._test_sess_db_path):
            os.remove(self._test_sess_db_path)

    def test_save(self):
        SimpleSessionManagerTest.test_save(self)
        self.assertTrue(os.path.exists(self._test_sess_db_path))

        conn = sqlite3.connect(self._test_sess_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT username, path FROM session WHERE hkey=?",
                       (self.test_hkey,))
        res = cursor.fetchone()
        conn.close()

        self.assertEqual(res[0], self.test_session.name)
        self.assertEqual(res[1], self.test_session.path)



