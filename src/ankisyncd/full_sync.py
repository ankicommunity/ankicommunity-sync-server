# -*- coding: utf-8 -*-

import logging
import os
from sqlite3 import dbapi2 as sqlite
import shutil
import sys
from webob.exc import HTTPBadRequest

from anki.db import DB
from anki.collection import Collection

logger = logging.getLogger("ankisyncd.media")
logger.setLevel(1)

class FullSyncManager:
    def test_db(self, db: DB):
        """
        :param anki.db.DB db: the database uploaded from the client.
        """
        if db.scalar("pragma integrity_check") != "ok":
            raise HTTPBadRequest(
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
        with open(temp_db_path, 'wb') as f:
            f.write(data)

        try:
            with DB(temp_db_path) as test_db:
                self.test_db(test_db)
        except sqlite.Error as e:
            raise HTTPBadRequest("Uploaded collection database file is "
                                 "corrupt.")

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
            with open(db_path, 'rb') as tmp:
                data = tmp.read()
        finally:
            col.reopen()
            # Reopen the media database
            col.media.connect()

        return data


def get_full_sync_manager(config):
    if "full_sync_manager" in config and config["full_sync_manager"]:  # load from config
        import importlib
        import inspect
        module_name, class_name = config['full_sync_manager'].rsplit('.', 1)
        module = importlib.import_module(module_name.strip())
        class_ = getattr(module, class_name.strip())

        if not FullSyncManager in inspect.getmro(class_):
            raise TypeError('''"full_sync_manager" found in the conf file but it doesn''t
                            inherit from FullSyncManager''')
        return class_(config)
    else:
        return FullSyncManager()
