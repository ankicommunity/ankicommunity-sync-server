# -*- coding: utf-8 -*-
import os
import shutil
import tempfile

from anki import Collection


class CollectionUtils:
    """
    Provides utility methods for creating, inspecting and manipulating anki
    collections.
    """

    def __init__(self):
        self.collections_to_close = []
        self.tempdir = tempfile.mkdtemp(prefix="CollectionUtils")
        self.master_db_path = None

    def __create_master_col(self):
        """
        Creates an empty master anki db that will be copied on each request
        for a new db. This is more efficient than initializing a new db each
        time.
        """

        file_path = os.path.join(self.tempdir, "collection.anki2")
        master_col = Collection(file_path)
        master_col.db.close()
        self.master_db_path = file_path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.clean_up()

    def __mark_collection_for_closing(self, collection):
        self.collections_to_close.append(collection)

    def clean_up(self):
        """
        Removes all files created by the Collection objects we issued and the
        master db file.
        """

        # Close collections.
        for col in self.collections_to_close:
            col.close()  # This also closes the media col.
        self.collections_to_close = []
        shutil.rmtree(self.tempdir)
        self.master_db_path = None

    def create_empty_col(self):
        """
        Returns a Collection object using a copy of our master db file.
        """

        if self.master_db_path is None:
            self.__create_master_col()

        file_descriptor, file_path = tempfile.mkstemp(dir=self.tempdir, suffix=".anki2")
        # Overwrite temp file with a copy of our master db.
        shutil.copy(self.master_db_path, file_path)
        collection = Collection(file_path)

        return collection
