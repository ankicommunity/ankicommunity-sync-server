# -*- coding: utf-8 -*-
import os
import sqlite3
import subprocess

from helpers.file_utils import FileUtils


class DBUtils(object):
    """Provides methods for creating and comparing sqlite databases."""

    def __init__(self):
        self.fileutils = FileUtils()

    def clean_up(self):
        self.fileutils.clean_up()

    def create_sqlite_db_with_sql(self, sql_string):
        """
        Creates an SQLite db and executes the passed sql statements on it.

        :param sql_string: the sql statements to execute on the newly created
                           db
        :return: the path to the created db file
        """

        db_path = self.fileutils.create_file_path(suffix=".anki2")
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.executescript(sql_string)
        connection.commit()
        connection.close()

        return db_path

    @staticmethod
    def sqlite_db_to_sql_string(database):
        """
        Returns a string containing the sql export of the database. Used for
        debugging.

        :param database: either the path to the SQLite db file or an open
                         connection to it
        :return: a string representing the sql export of the database
        """

        if type(database) == str:
            connection = sqlite3.connect(database)
        else:
            connection = database

        res = '\n'.join(connection.iterdump())

        if type(database) == str:
            connection.close()

        return res

    def media_dbs_differ(self, left_db_path, right_db_path, compare_timestamps=False):
        """
        Compares two media sqlite database files for equality. mtime and dirMod
        timestamps are not considered when comparing.

        :param left_db_path: path to the left db file
        :param right_db_path: path to the right db file
        :param compare_timestamps: flag determining if timestamp values
                                   (media.mtime and meta.dirMod) are included
                                   in the comparison
        :return: True if the specified databases differ, False else
        """

        if not os.path.isfile(left_db_path):
            raise IOError("file '" + left_db_path + "' does not exist")
        elif not os.path.isfile(right_db_path):
            raise IOError("file '" + right_db_path + "' does not exist")

        # Create temporary copies of the files to act on.
        left_db_path = self.fileutils.create_file_copy(left_db_path)
        right_db_path = self.fileutils.create_file_copy(right_db_path)

        if not compare_timestamps:
            # Set all timestamps that are not NULL to 0.
            for dbPath in [left_db_path, right_db_path]:
                connection = sqlite3.connect(dbPath)

                connection.execute("""UPDATE media SET mtime=0
                                      WHERE mtime IS NOT NULL""")

                connection.execute("""UPDATE meta SET dirMod=0
                                      WHERE rowid=1""")
                connection.commit()
                connection.close()

        return self.__sqlite_dbs_differ(left_db_path, right_db_path)

    def __sqlite_dbs_differ(self, left_db_path, right_db_path):
        """
        Uses the sqldiff cli tool to compare two sqlite files for equality.
        Returns True if the databases differ, False if they don't.

        :param left_db_path: path to the left db file
        :param right_db_path: path to the right db file
        :return: True if the specified databases differ, False else
        """

        command = ["/bin/sqldiff", left_db_path, right_db_path]

        try:
            child_process = subprocess.Popen(command,
                                             shell=False,
                                             stdout=subprocess.PIPE)
            stdout, stderr = child_process.communicate()
            exit_code = child_process.returncode

            if exit_code != 0 or stderr is not None:
                raise RuntimeError("Command {} encountered an error, exit "
                                   "code: {}, stderr: {}"
                                   .format(" ".join(command),
                                           exit_code,
                                           stderr))

            # Any output from sqldiff means the databases differ.
            return stdout != ""
        except OSError as err:
            raise err
