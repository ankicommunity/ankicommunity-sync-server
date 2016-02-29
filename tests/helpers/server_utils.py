# -*- coding: utf-8 -*-


import filecmp
import logging
import os
import ConfigParser
import shutil


from ankisyncd.sync_app import SyncApp, SyncCollectionHandler, SyncMediaHandler
from helpers.file_utils import FileUtils


class ServerUtils(object):
    def __init__(self):
        self.fileutils = FileUtils()

    def clean_up(self):
        self.fileutils.clean_up()

    def create_server_paths(self):
        """
        Creates temporary files and dirs for our app to use during tests.
        """

        auth = self.fileutils.create_file_path(suffix='.db',
                                               prefix='ankiserver_auth_db_')
        session = self.fileutils.create_file_path(suffix='.db',
                                                  prefix='ankiserver_session_db_')
        data = self.fileutils.create_dir(suffix='',
                                         prefix='ankiserver_data_root_')
        return {
            "auth_db": auth,
            "session_db": session,
            "data_root": data
        }

    @staticmethod
    def create_sync_app(server_paths, config_path):
        config = ConfigParser.SafeConfigParser()
        config.read(config_path)

        # Use custom files and dirs in settings.
        config.set("sync_app", "auth_db_path", server_paths["auth_db"])
        config.set("sync_app", "session_db_path", server_paths["session_db"])
        config.set("sync_app", "data_root", server_paths["data_root"])

        return SyncApp(config)

    def get_session_for_hkey(self, server, hkey):
        return server.session_manager.load(hkey)

    def get_thread_for_hkey(self, server, hkey):
        session = self.get_session_for_hkey(server, hkey)
        thread = session.get_thread()
        return thread

    def get_col_wrapper_for_hkey(self, server, hkey):
        print("getting col wrapper for hkey " + hkey)
        print("all session keys: " + str(server.session_manager.sessions.keys()))
        thread = self.get_thread_for_hkey(server, hkey)
        col_wrapper = thread.wrapper
        return col_wrapper

    def get_col_for_hkey(self, server, hkey):
        col_wrapper = self.get_col_wrapper_for_hkey(server, hkey)
        col_wrapper.open()  # Make sure the col is opened.
        return col_wrapper._CollectionWrapper__col

    def get_col_db_path_for_hkey(self, server, hkey):
        col = self.get_col_for_hkey(server, hkey)
        return col.db._path

    def get_syncer_for_hkey(self, server, hkey, syncer_type='collection'):
        col = self.get_col_for_hkey(server, hkey)

        session = self.get_session_for_hkey(server, hkey)

        syncer_type = syncer_type.lower()
        if syncer_type == 'collection':
            handler_method = SyncCollectionHandler.operations[0]
        elif syncer_type == 'media':
            handler_method = SyncMediaHandler.operations[0]

        return session.get_handler_for_operation(handler_method, col)

    def add_files_to_mediasyncer(self,
                                 media_syncer,
                                 filepaths,
                                 update_db=False,
                                 bump_last_usn=False):
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
