# -*- coding: utf-8 -*-


import os
import shutil
import tempfile


from anki import Collection
from helpers.file_utils import FileUtils


class CollectionUtils(object):
    """
    Provides utility methods for creating, inspecting and manipulating anki
    collections.
    """

    def __init__(self):
        self.collections_to_close = []
        self.fileutils = FileUtils()
        self.master_db_path = None

    def __create_master_col(self):
        """
        Creates an empty master anki db that will be copied on each request
        for a new db. This is more efficient than initializing a new db each
        time.
        """

        file_descriptor, file_path = tempfile.mkstemp(suffix=".anki2")
        os.close(file_descriptor)
        os.unlink(file_path)  # We only need the file path.
        master_col = Collection(file_path)
        self.__mark_col_paths_for_deletion(master_col)
        master_col.db.close()
        self.master_db_path = file_path

        self.fileutils.mark_for_deletion(self.master_db_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.clean_up()

    def __mark_collection_for_closing(self, collection):
        self.collections_to_close.append(collection)

    def __mark_col_paths_for_deletion(self, collection):
        """
        Marks the paths of all the database files and directories managed by
        the collection for later deletion.
        """
        self.fileutils.mark_for_deletion(collection.path)
        self.fileutils.mark_for_deletion(collection.media.dir())
        self.fileutils.mark_for_deletion(collection.media.col.path)

    def clean_up(self):
        """
        Removes all files created by the Collection objects we issued and the
        master db file.
        """

        # Close collections.
        for col in self.collections_to_close:
            col.close()  # This also closes the media col.
        self.collections_to_close = []

        # Remove the files created by the collections.
        self.fileutils.clean_up()

        self.master_db_path = None

    def create_empty_col(self):
        """
        Returns a Collection object using a copy of our master db file.
        """

        if self.master_db_path is None:
            self.__create_master_col()

        file_descriptor, file_path = tempfile.mkstemp(suffix=".anki2")

        # Overwrite temp file with a copy of our master db.
        shutil.copy(self.master_db_path, file_path)
        collection = Collection(file_path)

        self.__mark_collection_for_closing(collection)
        self.__mark_col_paths_for_deletion(collection)
        return collection

    @staticmethod
    def create_col_from_existing_db(db_file_path):
        """
        Returns a Collection object created from an existing anki db file.
        """

        return Collection(db_file_path)
