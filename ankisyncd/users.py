# -*- coding: utf-8 -*-


import binascii
from contextlib import closing
import hashlib
import logging
import os
import sqlite3 as sqlite


class UserManager:
    def __init__(self, auth_db_path, collection_path):
        self.auth_db_path = auth_db_path
        self.collection_path = collection_path

    def auth_db_exists(self):
        return os.path.isfile(self.auth_db_path)

    def user_list(self):
        if not self.auth_db_exists():
            self.create_auth_db()
            return []
        else:
            conn = sqlite.connect(self.auth_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT user FROM auth")
            rows = cursor.fetchall()
            conn.commit()
            conn.close()

            return [row[0] for row in rows]

    def user_exists(self, username):
        users = self.user_list()
        return username in users

    def del_user(self, username):
        if not self.auth_db_exists():
            self.create_auth_db()

        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        logging.info("Removing user '{}' from auth db."
                     .format(username))
        cursor.execute("DELETE FROM auth WHERE user=?", (username,))
        conn.commit()
        conn.close()

    def add_user(self, username, password):
        self._add_user_to_auth_db(username, password)
        self._create_user_dir(username)

    def add_users(self, users_data):
        for username, password in users_data:
            self.add_user(username, password)

    def _add_user_to_auth_db(self, username, password):
        if not self.auth_db_exists():
            self.create_auth_db()

        pass_hash = self._create_pass_hash(username, password)

        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        logging.info("Adding user '{}' to auth db.".format(username))
        cursor.execute("INSERT INTO auth VALUES (?, ?)",
                       (username, pass_hash))
        conn.commit()
        conn.close()

    @staticmethod
    def _create_pass_hash(username, password):
        salt = binascii.b2a_hex(os.urandom(8))
        pass_hash = (hashlib.sha256(username + password + salt).hexdigest() +
                     salt)
        return pass_hash

    def create_auth_db(self):
        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        logging.info("Creating auth db at {}."
                     .format(self.auth_db_path))
        cursor.execute("""CREATE TABLE IF NOT EXISTS auth
                          (user VARCHAR PRIMARY KEY, hash VARCHAR)""")
        conn.commit()
        conn.close()

    def _create_user_dir(self, username):
        user_dir_path = os.path.join(self.collection_path, username)
        if not os.path.isdir(user_dir_path):
            logging.info("Creating collection directory for user '{}' at {}"
                         .format(username, user_dir_path))
            os.makedirs(user_dir_path)
