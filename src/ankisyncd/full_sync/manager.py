import shutil
from sqlite3 import dbapi2 as sqlite

from anki.db import DB
from anki.collection import Collection

from ankisyncd.exceptions import BadRequestException


class FullSyncManager:
    def test_db(self, db: DB):
        """
        :param anki.db.DB db: the database uploaded from the client.
        """
        if db.scalar("pragma integrity_check") != "ok":
            raise BadRequestException(
                "Integrity check failed for uploaded collection database file."
            )

    def upload(self, col: Collection, data: bytes, session) -> str:
        """
        Uploads a sqlite database from the client to the sync server.

        :param anki.collection.Collectio col:
        :param bytes data: The binary sqlite database from the client.
        :param .sync_app.SyncUserSession session: The current session.
        """
        # Verify integrity of the received database file before replacing our
        # existing db.
        temp_db_path = session.get_collection_path() + ".tmp"
        with open(temp_db_path, "wb") as f:
            f.write(data)

        try:
            with DB(temp_db_path) as test_db:
                self.test_db(test_db)
        except sqlite.Error as e:
            raise BadRequestException(
                "Uploaded collection database file is " "corrupt."
            )

        # Overwrite existing db.
        col.close()
        try:
            shutil.copyfile(temp_db_path, session.get_collection_path())
        finally:
            col.reopen()
            # Reopen the media database
            col.media.connect()

        return "OK"

    def download(self, col: Collection, session) -> bytes:
        """Download the binary database.

        Performs a downgrade to database schema 11 before sending the database
        to the client.

        :param anki.collection.Collection col:
        :param .sync_app.SyncUserSession session:

        :return bytes: the binary sqlite3 database
        """
        col.close(downgrade=True)
        db_path = session.get_collection_path()
        try:
            with open(db_path, "rb") as tmp:
                data = tmp.read()
        finally:
            col.reopen()
            # Reopen the media database
            col.media.connect()

        return data
