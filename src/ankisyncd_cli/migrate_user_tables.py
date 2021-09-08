#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script updates the auth and session sqlite3 databases to use the
more compatible `username` column instead of `user`, which is a reserved
word in many other SQL dialects.
"""
import os
import sys
path = os.path.realpath(os.path.abspath(os.path.join(__file__, '../')))
sys.path.insert(0, os.path.dirname(path))

import sqlite3
import ankisyncd.config
conf = ankisyncd.config.load()


def main():

    if os.path.isfile(conf["auth_db_path"]):
        conn = sqlite3.connect(conf["auth_db_path"])

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sqlite_master "
                             "WHERE sql LIKE '%user VARCHAR PRIMARY KEY%' "
                             "AND tbl_name = 'auth'")
        res = cursor.fetchone()

        if res is not None:
            cursor.execute("ALTER TABLE auth RENAME TO auth_old")
            cursor.execute("CREATE TABLE auth (username VARCHAR PRIMARY KEY, hash VARCHAR)")
            cursor.execute("INSERT INTO auth (username, hash) SELECT user, hash FROM auth_old")
            cursor.execute("DROP TABLE auth_old")
            conn.commit()
            print("Successfully updated table 'auth'")
        else:
            print("No outdated 'auth' table found.")

        conn.close()
    else:
        print("No auth DB found at the configured 'auth_db_path' path.")

    if os.path.isfile(conf["session_db_path"]):
        conn = sqlite3.connect(conf["session_db_path"])

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sqlite_master "
                             "WHERE sql LIKE '%user VARCHAR%' "
                             "AND tbl_name = 'session'")
        res = cursor.fetchone()

        if res is not None:
            cursor.execute("ALTER TABLE session RENAME TO session_old")
            cursor.execute("CREATE TABLE session (hkey VARCHAR PRIMARY KEY, skey VARCHAR, "
                           "username VARCHAR, path VARCHAR)")
            cursor.execute("INSERT INTO session (hkey, skey, username, path) "
                           "SELECT hkey, skey, user, path FROM session_old")
            cursor.execute("DROP TABLE session_old")
            conn.commit()
            print("Successfully updated table 'session'")
        else:
            print("No outdated 'session' table found.")

        conn.close()
    else:
        print("No session DB found at the configured 'session_db_path' path.")


if __name__ == "__main__":
    main()
