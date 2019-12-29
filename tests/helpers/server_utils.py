# -*- coding: utf-8 -*-
import configparser
import logging
import os
import shutil
import tempfile

import anki.utils

from ankisyncd.sync_app import SyncApp, SyncCollectionHandler, SyncMediaHandler


def create_server_paths():
    """
    Creates temporary files and dirs for our app to use during tests.
    """
    dir = tempfile.mkdtemp(prefix="ServerUtils")
    os.mkdir(os.path.join(dir, "data"))

    return {
        "auth_db_path": os.path.join(dir, "auth.db"),
        "session_db_path": os.path.join(dir, "session.db"),
        "data_root": os.path.join(dir, "data"),
    }

def create_sync_app(server_paths, config_path):
    config = configparser.ConfigParser()
    config.read(config_path)

    # Use custom files and dirs in settings.
    config['sync_app'].update(server_paths)

    return SyncApp(config['sync_app'])

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

def add_files_to_client_mediadb(media, filepaths, update_db=False):
    for filepath in filepaths:
        logging.debug("Adding file '{}' to client media DB".format(filepath))
        # Import file into media dir.
        media.addFile(filepath)

    if update_db:
        media.findChanges()  # Write changes to db.

def add_files_to_server_mediadb(media, filepaths):
    for filepath in filepaths:
        logging.debug("Adding file '{}' to server media DB".format(filepath))
        fname = os.path.basename(filepath)
        with open(filepath, 'rb') as infile:
            data = infile.read()
            csum = anki.utils.checksum(data)

            with open(os.path.join(media.dir(), fname), 'wb') as f:
                f.write(data)
            media.db.execute("INSERT INTO media VALUES (?, ?, ?)", fname, media.lastUsn() + 1, csum)
            media.db.commit()
