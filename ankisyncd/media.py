# Based on anki.media.MediaManager, © Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Original source: https://raw.githubusercontent.com/dae/anki/62481ddc1aa78430cb8114cbf00a7739824318a8/anki/media.py

import logging
import re
import os
import os.path

import anki.db

logger = logging.getLogger("ankisyncd.media")


class ServerMediaManager:
    def __init__(self, col):
        self._dir = re.sub(r"(?i)\.(anki2)$", ".media", col.path)
        self.connect()

    def connect(self):
        path = self.dir() + ".server.db"
        create = not os.path.exists(path)
        self.db = anki.db.DB(path)
        if create:
            self.db.executescript(
                """CREATE TABLE media (
                       fname TEXT NOT NULL PRIMARY KEY,
                       usn INT NOT NULL,
                       csum TEXT -- null if deleted
                   );
                CREATE INDEX idx_media_usn ON media (usn);"""
            )
            oldpath = self.dir() + ".db2"
            if os.path.exists(oldpath):
                logger.info("Found client media database, migrating contents")
                self.db.execute("ATTACH ? AS old", oldpath)
                self.db.execute(
                    "INSERT INTO media SELECT fname, lastUsn, csum FROM old.media, old.meta"
                )
                self.db.commit()
                self.db.execute("DETACH old")

    def close(self):
        self.db.close()

    def dir(self):
        return self._dir

    def lastUsn(self):
        return self.db.scalar("SELECT max(usn) FROM media") or 0

    def mediaCount(self):
        return self.db.scalar("SELECT count() FROM media WHERE csum IS NOT NULL")

    # used only in unit tests
    def syncInfo(self, fname):
        return self.db.first("SELECT csum, 0 FROM media WHERE fname=?", fname)

    def syncDelete(self, fname):
        fpath = os.path.join(self.dir(), fname)
        if os.path.exists(fpath):
            os.remove(fpath)
        self.db.execute(
            "UPDATE media SET csum = NULL, usn = ? WHERE fname = ?",
            self.lastUsn() + 1,
            fname,
        )
