# -*- coding: utf-8 -*-
import os
import sqlite3
import tempfile
import unittest

from anki.consts import SYNC_VER

from ankisyncd.sync_app import SyncCollectionHandler
from ankisyncd.sync_app import SyncUserSession

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
            ','.join(('ankidesktop', '2.1.9 (dev)', 'lin::')),
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


class SyncAppTest(unittest.TestCase):
    pass
