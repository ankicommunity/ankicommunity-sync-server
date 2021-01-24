# Based on anki.media.MediaManager, © Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Original source: https://raw.githubusercontent.com/dae/anki/62481ddc1aa78430cb8114cbf00a7739824318a8/anki/media.py

import logging
import re
import os
import os.path

import anki.db
from anki.media import MediaManager

logger = logging.getLogger("ankisyncd.media")

class ServerMediaManager(MediaManager):
    def __init__(self, col, server=True):
        super().__init__(col, server)
        self._dir = re.sub(r"(?i)\.(anki2)$", ".media", col.path)
        self.connect()

    def addMedia(self, media_to_add):
        self._db.executemany(
            "INSERT OR REPLACE INTO media VALUES (?,?,?)",
            media_to_add
        )
        self._db.commit()

    def changes(self, lastUsn):
        return self._db.execute("select fname,usn,csum from media order by usn desc limit ?", self.lastUsn() - lastUsn)
        
    def connect(self):
        path = self.dir() + ".server.db"
        create = not os.path.exists(path)
        self._db = anki.db.DB(path)
        if create:
            self._db.executescript(
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
                self._db.execute("ATTACH ? AS old", oldpath)
                self._db.execute(
                    "INSERT INTO media SELECT fname, lastUsn, csum FROM old.media, old.meta"
                )
                self._db.commit()
                self._db.execute("DETACH old")

    def close(self):
        self._db.close()

    def dir(self):
        return self._dir

    def lastUsn(self):
        return self._db.scalar("SELECT max(usn) FROM media") or 0

    def mediaCount(self):
        return self._db.scalar("SELECT count() FROM media WHERE csum IS NOT NULL")

    # used only in unit tests
    def syncInfo(self, fname):
        return self._db.first("SELECT csum, 0 FROM media WHERE fname=?", fname)

    def syncDelete(self, fname):
        fpath = os.path.join(self.dir(), fname)
        if os.path.exists(fpath):
            os.remove(fpath)
        self._db.execute(
            "UPDATE media SET csum = NULL, usn = ? WHERE fname = ?",
            self.lastUsn() + 1,
            fname,
        )
        self._db.commit()
