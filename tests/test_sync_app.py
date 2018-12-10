# -*- coding: utf-8 -*-
import os
import sqlite3
import tempfile
import unittest

from anki.consts import SYNC_VER

from ankisyncd.sync_app import SyncCollectionHandler
from ankisyncd.sync_app import SyncUserSession
from ankisyncd.sync_app import SimpleSessionManager
from ankisyncd.sync_app import SqliteSessionManager

from collection_test_base import CollectionTestBase


class SyncCollectionHandlerTest(CollectionTestBase):
    def setUp(self):
        CollectionTestBase.setUp(self)
        self.syncCollectionHandler = SyncCollectionHandler(self.collection)

    def tearDown(self):
        CollectionTestBase.tearDown(self)
        self.syncCollectionHandler = None

    def test_old_client(self):
        old = (
            ','.join(('ankidesktop', '2.0.12', 'lin::')),
            ','.join(('ankidesktop', '2.0.26', 'lin::')),
            ','.join(('ankidroid', '2.1', '')),
            ','.join(('ankidroid', '2.2', '')),
            ','.join(('ankidroid', '2.2.2', '')),
            ','.join(('ankidroid', '2.3alpha3', '')),
        )

        current = (
            None,
            ','.join(('ankidesktop', '2.0.27', 'lin::')),
            ','.join(('ankidesktop', '2.0.32', 'lin::')),
            ','.join(('ankidesktop', '2.1.0', 'lin::')),
            ','.join(('ankidesktop', '2.1.6-beta2', 'lin::')),
            ','.join(('ankidroid', '2.2.3', '')),
            ','.join(('ankidroid', '2.3alpha4', '')),
            ','.join(('ankidroid', '2.3alpha5', '')),
            ','.join(('ankidroid', '2.3beta1', '')),
            ','.join(('ankidroid', '2.3', '')),
            ','.join(('ankidroid', '2.9', '')),
        )

        for cv in old:
            if not SyncCollectionHandler._old_client(cv):
                raise AssertionError("old_client(\"%s\") is False" % cv)

        for cv in current:
            if SyncCollectionHandler._old_client(cv):
                raise AssertionError("old_client(\"%s\") is True" % cv)

    def test_meta(self):
        meta = self.syncCollectionHandler.meta(v=SYNC_VER)
        self.assertEqual(meta['scm'], self.collection.scm)
        self.assertTrue((type(meta['ts']) == int) and meta['ts'] > 0)
        self.assertEqual(meta['mod'], self.collection.mod)
        self.assertEqual(meta['usn'], self.collection._usn)
        self.assertEqual(meta['musn'], self.collection.media.lastUsn())
        self.assertEqual(meta['msg'], '')
        self.assertEqual(meta['cont'], True)


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
        cursor.execute("SELECT user, path FROM session WHERE hkey=?",
                       (self.test_hkey,))
        res = cursor.fetchone()
        conn.close()

        self.assertEqual(res[0], self.test_session.name)
        self.assertEqual(res[1], self.test_session.path)


class SyncAppTest(unittest.TestCase):
    pass
