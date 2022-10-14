# -*- coding: utf-8 -*-
import os
import sqlite3 as sqlite
from anki.media import MediaManager
from anki.db import DB

mediamanager_orig_funcs = {
    "findChanges": None,
    "mediaChangesZip": None,
    "addFilesFromZip": None,
    "syncDelete": None,
    "_logChanges": None,
}

db_orig_funcs = {"__init__": None}


def monkeypatch_mediamanager():
    """
    Monkey patches anki.media.MediaManager's methods so they chdir to
    self.dir() before acting on its media directory and chdir back to the
    original cwd after finishing.
    """

    def make_cwd_safe(original_func):
        mediamanager_orig_funcs["findChanges"] = MediaManager.findChanges

        def wrapper(instance, *args):
            old_cwd = os.getcwd()
            os.chdir(instance.dir())

            res = original_func(instance, *args)

            os.chdir(old_cwd)
            return res

        return wrapper

    MediaManager.findChanges = make_cwd_safe(MediaManager.findChanges)


def unpatch_mediamanager():
    """Undoes monkey patches to Anki's MediaManager."""

    MediaManager.findChanges = mediamanager_orig_funcs["findChanges"]

    mediamanager_orig_funcs["findChanges"] = None


def monkeypatch_db():
    """
    Monkey patches Anki's DB.__init__ to connect to allow access to the db
    connection from more than one thread, so that we can inspect and modify
    the db created in the app in our test code.
    """
    db_orig_funcs["__init__"] = DB.__init__

    def patched___init__(self, path, text=None, timeout=0):
        # Code taken from Anki's DB.__init__()
        # Allow more than one thread to use this connection.
        self._db = sqlite.connect(path, timeout=timeout, check_same_thread=False)
        if text:
            self._db.text_factory = text
        self._path = path
        self.echo = os.environ.get("DBECHO")  # echo db modifications
        self.mod = False  # flag that db has been modified?

    DB.__init__ = patched___init__


def unpatch_db():
    """Undoes monkey patches to Anki's DB."""

    DB.__init__ = db_orig_funcs["__init__"]
    db_orig_funcs["__init__"] = None
