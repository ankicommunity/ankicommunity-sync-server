# -*- coding: utf-8 -*-


from cStringIO import StringIO
import json
import logging
import logging.config
import os
import random
import shutil
import tempfile
import unicodedata
import zipfile


from anki.consts import SYNC_ZIP_SIZE
from anki.utils import checksum


class FileUtils(object):
    """
    Provides utility methods for creating temporary files and directories. All
    created files and dirs are recursively removed when clean_up() is called.
    Supports the with statement.
    """

    def __init__(self):
        self.paths_to_delete = []

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.clean_up()

    def clean_up(self):
        """
        Recursively removes all files and directories created by this instance.
        """

        # Change cwd to a dir we're not about to delete so later calls to
        # os.getcwd() and similar functions don't raise Exceptions.
        os.chdir("/tmp")

        # Error callback for shutil.rmtree().
        def on_error(func, path, excinfo):
            logging.error("Error removing file: func={}, path={}, excinfo={}"
                          .format(func, path, excinfo))

        for path in self.paths_to_delete:
            if os.path.isfile(path):
                logging.debug("Removing temporary file '{}'.".format(path))
                os.remove(path)
            elif os.path.isdir(path):
                logging.debug(("Removing temporary dir tree '{}' with " +
                               "files {}").format(path, os.listdir(path)))
                shutil.rmtree(path, onerror=on_error)

        self.paths_to_delete = []

    def mark_for_deletion(self, path):
        self.paths_to_delete.append(path)

    def create_file(self, suffix='', prefix='tmp'):
        file_descriptor, file_path = tempfile.mkstemp(suffix=suffix,
                                                      prefix=prefix)
        self.mark_for_deletion(file_path)
        return file_path

    def create_dir(self, suffix='', prefix='tmp'):
        dir_path = tempfile.mkdtemp(suffix=suffix,
                                    prefix=prefix)
        self.mark_for_deletion(dir_path)
        return dir_path

    def create_file_path(self, suffix='', prefix='tmp'):
        """Generates a file path."""

        file_path = self.create_file(suffix, prefix)
        os.unlink(file_path)
        return file_path

    def create_dir_path(self, suffix='', prefix='tmp'):
        dir_path = self.create_dir(suffix, prefix)
        os.rmdir(dir_path)
        return dir_path

    def create_named_file(self, filename, file_contents=None):
        """
        Creates a temporary file with a custom name within a new temporary
        directory and marks that parent dir for recursive deletion method.
        """

        # We need to create a parent directory for the file so we can freely
        # choose the file name .
        temp_file_parent_dir = tempfile.mkdtemp(prefix="anki")
        self.mark_for_deletion(temp_file_parent_dir)

        file_path = os.path.join(temp_file_parent_dir, filename)

        if file_contents is not None:
            open(file_path, 'w').write(file_contents)

        return file_path

    def create_named_file_path(self, filename):
        file_path = self.create_named_file(filename)
        return file_path

    def create_file_copy(self, path):
        basename = os.path.basename(path)
        temp_file_path = self.create_named_file_path(basename)
        shutil.copyfile(path, temp_file_path)
        return temp_file_path

    def create_named_files(self, filenames_and_data):
        """
        Creates temporary files within the same new temporary parent directory
        and marks that parent for recursive deletion.

        :param filenames_and_data: list of tuples (filename, file contents)
        :return: list of paths to the created files
        """

        temp_files_parent_dir = tempfile.mkdtemp(prefix="anki")
        self.mark_for_deletion(temp_files_parent_dir)

        file_paths = []
        for filename, file_contents in filenames_and_data:
            path = os.path.join(temp_files_parent_dir, filename)
            file_paths.append(path)
            if file_contents is not None:
                open(path, 'w').write(file_contents)

        return file_paths

    @staticmethod
    def create_zip_with_existing_files(file_paths):
        """
        The method zips existing files and returns the zip data. Logic is
        adapted from Anki Desktop's MediaManager.mediaChangesZip().

        :param file_paths: the paths of the files to include in the zip
        :type file_paths: list
        :return: the data of the created zip file
        """

        file_buffer = StringIO()
        zip_file = zipfile.ZipFile(file_buffer,
                                   'w',
                                   compression=zipfile.ZIP_DEFLATED)

        meta = []
        sz = 0

        for count, filePath in enumerate(file_paths):
            zip_file.write(filePath, str(count))
            normname = unicodedata.normalize(
                "NFC",
                os.path.basename(filePath)
            )
            meta.append((normname, str(count)))

            sz += os.path.getsize(filePath)
            if sz >= SYNC_ZIP_SIZE:
                break

        zip_file.writestr("_meta", json.dumps(meta))
        zip_file.close()

        return file_buffer.getvalue()
