# -*- coding: utf-8 -*-
import binascii
import hashlib
import logging
import os
import sqlite3 as sqlite

logger = logging.getLogger("ankisyncd.users")


class SimpleUserManager:
    """A simple user manager that always allows any user."""

    def __init__(self, collection_path=''):
        self.collection_path = collection_path

    def authenticate(self, username, password):
        """
        Returns True if this username is allowed to connect with this password.
        False otherwise. Override this to change how users are authenticated.
        """

        return True

    def userdir(self, username):
        """
        Returns the directory name for the given user. By default, this is just
        the username. Override this to adjust the mapping between users and
        their directory.
        """

        return username

    def _create_user_dir(self, username):
        user_dir_path = os.path.join(self.collection_path, username)
        if not os.path.isdir(user_dir_path):
            logger.info("Creating collection directory for user '{}' at {}"
                         .format(username, user_dir_path))
            os.makedirs(user_dir_path)


class SqliteUserManager(SimpleUserManager):
    """Authenticates users against a SQLite database."""

    def __init__(self, auth_db_path, collection_path=None):
        SimpleUserManager.__init__(self, collection_path)
        self.auth_db_path = os.path.realpath(auth_db_path)

    def auth_db_exists(self):
        return os.path.isfile(self.auth_db_path)

    def user_list(self):
        if not self.auth_db_exists():
            raise ValueError("Auth DB {} doesn't exist".format(self.auth_db_path))

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
            raise ValueError("Auth DB {} doesn't exist".format(self.auth_db_path))

        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        logger.info("Removing user '{}' from auth db".format(username))
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
        logger.info("Adding user '{}' to auth db.".format(username))
        cursor.execute("INSERT INTO auth VALUES (?, ?)",
                       (username, pass_hash))
        conn.commit()
        conn.close()

    def set_password_for_user(self, username, new_password):
        if not self.auth_db_exists():
            raise ValueError("Auth DB {} doesn't exist".format(self.auth_db_path))
        elif not self.user_exists(username):
            raise ValueError("User {} doesn't exist".format(username))

        hash = self._create_pass_hash(username, new_password)

        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE auth SET hash=? WHERE user=?", (hash, username))
        conn.commit()
        conn.close()

        logger.info("Changed password for user {}".format(username))

    def authenticate(self, username, password):
        """Returns True if this username is allowed to connect with this password. False otherwise."""

        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        param = (username,)
        cursor.execute("SELECT hash FROM auth WHERE user=?", param)
        db_hash = cursor.fetchone()
        conn.close()

        if db_hash is None:
            logger.info("Authentication failed for nonexistent user {}."
                         .format(username))
            return False

        expected_value = str(db_hash[0])
        salt = self._extract_salt(expected_value)

        hashobj = hashlib.sha256()
        hashobj.update((username + password + salt).encode())
        actual_value = hashobj.hexdigest() + salt

        if actual_value == expected_value:
            logger.info("Authentication succeeded for user {}".format(username))
            return True
        else:
            logger.info("Authentication failed for user {}".format(username))
            return False

    @staticmethod
    def _extract_salt(hash):
        return hash[-16:]

    @staticmethod
    def _create_pass_hash(username, password):
        salt = binascii.b2a_hex(os.urandom(8))
        pass_hash = (hashlib.sha256((username + password).encode() + salt).hexdigest() +
                     salt.decode())
        return pass_hash

    def create_auth_db(self):
        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        logger.info("Creating auth db at {}."
                     .format(self.auth_db_path))
        cursor.execute("""CREATE TABLE IF NOT EXISTS auth
                          (user VARCHAR PRIMARY KEY, hash VARCHAR)""")
        conn.commit()
        conn.close()
