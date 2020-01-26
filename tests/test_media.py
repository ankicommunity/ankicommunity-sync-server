import os.path
import unittest

import ankisyncd.media
import helpers.collection_utils


class ServerMediaManagerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.colutils = helpers.collection_utils.CollectionUtils()

    @classmethod
    def tearDownClass(cls):
        cls.colutils.clean_up()
        cls.colutils = None

    def test_upgrade(self):
        col = self.colutils.create_empty_col()
        cm = col.media

        fpath = os.path.join(cm.dir(), "file")
        with open(fpath + "A", "w") as f:
            f.write("some contents")
        with open(fpath + "B", "w") as f:
            f.write("other contents")
        cm._logChanges()

        self.assertEqual(
            set(cm.db.execute("SELECT fname, csum FROM media")),
            {
                ("fileA", "53059abba1a72c7aff34a3eaf7fef10ed65541ce"),
                ("fileB", "a5ae546046d09559399c80fa7076fb10f1ce4bcd"),
            },
        )
        cm.setLastUsn(161)

        sm = ankisyncd.media.ServerMediaManager(col)
        self.assertEqual(
            list(sm.db.execute("SELECT fname, csum FROM media")),
            list(cm.db.execute("SELECT fname, csum FROM media")),
        )
        self.assertEqual(cm.lastUsn(), sm.lastUsn())
        self.assertEqual(list(sm.db.execute("SELECT usn FROM media")), [(161,), (161,)])

    def test_mediaChanges_lastUsn_order(self):
        col = self.colutils.create_empty_col()
        col.media = ankisyncd.media.ServerMediaManager(col)
        mh = ankisyncd.sync_app.SyncMediaHandler(col)
        mh.col.media.db.execute("""
            INSERT INTO media (fname, usn, csum)
            VALUES
                ('fileA', 101, '53059abba1a72c7aff34a3eaf7fef10ed65541ce'),
                ('fileB', 100, 'a5ae546046d09559399c80fa7076fb10f1ce4bcd')
        """)

        # anki assumes mh.col.media.lastUsn() == mh.mediaChanges()['data'][-1][1]
        # ref: anki/sync.py:720 (commit cca3fcb2418880d0430a5c5c2e6b81ba260065b7)
        self.assertEqual(mh.mediaChanges(lastUsn=99)['data'][-1][1], mh.col.media.lastUsn())
