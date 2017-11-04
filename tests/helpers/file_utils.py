# -*- coding: utf-8 -*-
from io import BytesIO
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


def create_named_file(filename, file_contents=None):
    """
    Creates a temporary file with a custom name within a new temporary
    directory and marks that parent dir for recursive deletion method.
    """

    # We need to create a parent directory for the file so we can freely
    # choose the file name .
    temp_file_parent_dir = tempfile.mkdtemp(prefix="named_file")

    file_path = os.path.join(temp_file_parent_dir, filename)

    if file_contents is not None:
        open(file_path, 'w').write(file_contents)

    return file_path


def create_zip_with_existing_files(file_paths):
    """
    The method zips existing files and returns the zip data. Logic is
    adapted from Anki Desktop's MediaManager.mediaChangesZip().

    :param file_paths: the paths of the files to include in the zip
    :type file_paths: list
    :return: the data of the created zip file
    """

    file_buffer = BytesIO()
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


def get_asset_path(relative_file_path):
    """
    Retrieves the path of a file for testing from the "assets" directory.

    :param relative_file_path: the name of the file to retrieve, relative
                               to the "assets" directory
    :return: the absolute path to the file in the "assets" directory.
    """

    join = os.path.join

    script_dir = os.path.dirname(os.path.realpath(__file__))
    support_dir = join(script_dir, os.pardir, "assets")
    res = join(support_dir, relative_file_path)
    return res
