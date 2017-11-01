# -*- coding: utf-8 -*-
import os
import sqlite3
import subprocess


def from_sql(path, sql):
    """
    Creates an SQLite db and executes the passed sql statements on it.

    :param path: the path to the created db file
    :param sql: the sql statements to execute on the newly created db
    """

    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.executescript(sql)
    connection.commit()
    connection.close()


def to_sql(database):
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


def diff(left_db_path, right_db_path):
    """
    Uses the sqldiff cli tool to compare two sqlite files for equality.
    Returns True if the databases differ, False if they don't.

    :param left_db_path: path to the left db file
    :param right_db_path: path to the right db file
    :return: True if the specified databases differ, False else
    """

    command = ["sqldiff", left_db_path, right_db_path]

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
