# -*- coding: utf-8 -*-

import unittest

import ankisyncd
from ankisyncd.sync_app import SyncCollectionHandler
from ankisyncd.sync_app import SyncApp

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
        self.assertEqual(meta[4], self.collection.media.usn())

        meta = self.syncCollectionHandler.meta(version_info[1])
        self.assertEqual(meta[0], self.collection.mod)
        self.assertEqual(meta[1], self.collection.scm)
        self.assertEqual(meta[2], self.collection._usn)
        self.assertTrue((type(meta[3]) == int) and meta[3] > 0)
        self.assertEqual(meta[4], self.collection.media.usn())

        meta = self.syncCollectionHandler.meta(version_info[2])
        self.assertEqual(meta['scm'], self.collection.scm)
        self.assertTrue((type(meta['ts']) == int) and meta['ts'] > 0)
        self.assertEqual(meta['mod'], self.collection.mod)
        self.assertEqual(meta['usn'], self.collection._usn)
        self.assertEqual(meta['musn'], self.collection.media.usn())
        self.assertEqual(meta['msg'], '')
        self.assertEqual(meta['cont'], True)


class SyncAppTest(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
