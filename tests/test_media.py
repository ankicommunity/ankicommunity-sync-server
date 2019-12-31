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
