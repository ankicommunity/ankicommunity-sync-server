# -*- coding: utf-8 -*-
import configparser
import logging
import os
import shutil
import tempfile

from ankisyncd.sync_app import SyncApp, SyncCollectionHandler, SyncMediaHandler


def create_server_paths():
    """
    Creates temporary files and dirs for our app to use during tests.
    """
    dir = tempfile.mkdtemp(prefix="ServerUtils")
    os.mkdir(os.path.join(dir, "data"))

    return {
        "auth_db": os.path.join(dir, "auth.db"),
        "session_db": os.path.join(dir, "session.db"),
        "data_root": os.path.join(dir, "data"),
    }

def create_sync_app(server_paths, config_path):
    config = configparser.SafeConfigParser()
    config.read(config_path)

    # Use custom files and dirs in settings.
    config.set("sync_app", "auth_db_path", server_paths["auth_db"])
    config.set("sync_app", "session_db_path", server_paths["session_db"])
    config.set("sync_app", "data_root", server_paths["data_root"])

    return SyncApp(config)

def get_session_for_hkey(server, hkey):
    return server.session_manager.load(hkey)

def get_thread_for_hkey(server, hkey):
    session = get_session_for_hkey(server, hkey)
    thread = session.get_thread()
    return thread

def get_col_wrapper_for_hkey(server, hkey):
    thread = get_thread_for_hkey(server, hkey)
    col_wrapper = thread.wrapper
    return col_wrapper

def get_col_for_hkey(server, hkey):
    col_wrapper = get_col_wrapper_for_hkey(server, hkey)
    col_wrapper.open()  # Make sure the col is opened.
    return col_wrapper._CollectionWrapper__col

def get_col_db_path_for_hkey(server, hkey):
    col = get_col_for_hkey(server, hkey)
    return col.db._path

def get_syncer_for_hkey(server, hkey, syncer_type='collection'):
    col = get_col_for_hkey(server, hkey)

    session = get_session_for_hkey(server, hkey)

    syncer_type = syncer_type.lower()
    if syncer_type == 'collection':
        handler_method = SyncCollectionHandler.operations[0]
    elif syncer_type == 'media':
        handler_method = SyncMediaHandler.operations[0]

    return session.get_handler_for_operation(handler_method, col)

def add_files_to_mediasyncer(media_syncer, filepaths,
                             update_db=False, bump_last_usn=False):
    """
    If bumpLastUsn is True, the media syncer's lastUsn will be incremented
    once for each added file. Use this when adding files to the server.
    """

    for filepath in filepaths:
        logging.debug("Adding file '{}' to mediaSyncer".format(filepath))
        # Import file into media dir.
        media_syncer.col.media.addFile(filepath)
        if bump_last_usn:
            # Need to bump lastUsn once for each file.
            media_manager = media_syncer.col.media
            media_manager.setLastUsn(media_syncer.col.media.lastUsn() + 1)

    if update_db:
        media_syncer.col.media.findChanges()  # Write changes to db.
