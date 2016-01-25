# -*- coding: utf-8 -*-

import binascii
import hashlib
import os
import sqlite3
import tempfile
import unittest

from AnkiServer.apps.sync_app import SyncCollectionHandler
from AnkiServer.apps.sync_app import SimpleUserManager
from AnkiServer.apps.sync_app import SqliteUserManager
from AnkiServer.apps.sync_app import SyncUserSession
from AnkiServer.apps.sync_app import SimpleSessionManager
from AnkiServer.apps.sync_app import SqliteSessionManager
from AnkiServer.apps.sync_app import SyncApp

from CollectionTestBase import CollectionTestBase


class SyncCollectionHandlerTest(CollectionTestBase):

    def setUp(self):
        CollectionTestBase.setUp(self)
        self.syncCollectionHandler = SyncCollectionHandler(self.collection)

    def tearDown(self):
        CollectionTestBase.tearDown(self)
        self.syncCollectionHandler = None

    def test_meta(self):
        version_info = (None,
                        ','.join(('ankidesktop', '2.0.12', 'lin::')),
                        ','.join(('ankidesktop', '2.0.32', 'lin::')))

        meta = self.syncCollectionHandler.meta(version_info[0])
        self.assertEqual(meta[0], self.collection.mod)
        self.assertEqual(meta[1], self.collection.scm)
        self.assertEqual(meta[2], self.collection._usn)
        self.assertTrue((type(meta[3]) == int) and meta[3] > 0)
        self.assertEqual(meta[4], self.collection.media.lastUsn())

        meta = self.syncCollectionHandler.meta(version_info[1])
        self.assertEqual(meta[0], self.collection.mod)
        self.assertEqual(meta[1], self.collection.scm)
        self.assertEqual(meta[2], self.collection._usn)
        self.assertTrue((type(meta[3]) == int) and meta[3] > 0)
        self.assertEqual(meta[4], self.collection.media.lastUsn())

        meta = self.syncCollectionHandler.meta(version_info[2])
        self.assertEqual(meta['scm'], self.collection.scm)
        self.assertTrue((type(meta['ts']) == int) and meta['ts'] > 0)
        self.assertEqual(meta['mod'], self.collection.mod)
        self.assertEqual(meta['usn'], self.collection._usn)
        self.assertEqual(meta['musn'], self.collection.media.lastUsn())
        self.assertEqual(meta['msg'], '')
        self.assertEqual(meta['cont'], True)


class SimpleUserManagerTest(unittest.TestCase):
    _good_test_un = 'username'
    _good_test_pw = 'password'

    _bad_test_un = 'notAUsername'
    _bad_test_pw = 'notAPassword'

    def setUp(self):
        self._user_manager = SimpleUserManager()

    def tearDown(self):
        self._user_manager = None

    def test_authenticate(self):
        self.assertTrue(self._user_manager.authenticate(self._good_test_un,
                                                        self._good_test_pw))

        self.assertTrue(self._user_manager.authenticate(self._bad_test_un,
                                                        self._bad_test_pw))

        self.assertTrue(self._user_manager.authenticate(self._good_test_un,
                                                        self._bad_test_pw))

        self.assertTrue(self._user_manager.authenticate(self._bad_test_un,
                                                        self._good_test_pw))

    def test_username2dirname(self):
        dirname = self._user_manager.username2dirname(self._good_test_un)
        self.assertEqual(dirname, self._good_test_un)


class SqliteUserManagerTest(SimpleUserManagerTest):
    file_descriptor, _test_auth_db_path = tempfile.mkstemp(suffix=".db")
    os.close(file_descriptor)
    os.unlink(_test_auth_db_path)

    def _create_test_auth_db(self, db_path, username, password):
        if os.path.exists(db_path):
            os.remove(db_path)

        salt = binascii.b2a_hex(os.urandom(8))
        crypto_hash = hashlib.sha256(username+password+salt).hexdigest()+salt

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""CREATE TABLE IF NOT EXISTS auth
                       (user VARCHAR PRIMARY KEY, hash VARCHAR)""")

        cursor.execute("INSERT INTO auth VALUES (?, ?)", (username, crypto_hash))

        conn.commit()
        conn.close()

    def setUp(self):
        self._create_test_auth_db(self._test_auth_db_path,
                                  self._good_test_un,
                                  self._good_test_pw)
        self._user_manager = SqliteUserManager(self._test_auth_db_path)

    def tearDown(self):
        if os.path.exists(self._test_auth_db_path):
            os.remove(self._test_auth_db_path)

    def test_authenticate(self):
        self.assertTrue(self._user_manager.authenticate(self._good_test_un,
                                                        self._good_test_pw))

        self.assertFalse(self._user_manager.authenticate(self._bad_test_un,
                                                         self._bad_test_pw))

        self.assertFalse(self._user_manager.authenticate(self._good_test_un,
                                                         self._bad_test_pw))

        self.assertFalse(self._user_manager.authenticate(self._bad_test_un,
                                                         self._good_test_pw))


class SimpleSessionManagerTest(unittest.TestCase):
    test_hkey = '1234567890'
    test_session = SyncUserSession('testName', 'testPath', None, None)

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
        cursor.execute("SELECT user, path FROM session WHERE hkey=?",
                       (self.test_hkey,))
        res = cursor.fetchone()
        conn.close()

        self.assertEqual(res[0], self.test_session.name)
        self.assertEqual(res[1], self.test_session.path)


class SyncAppTest(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
