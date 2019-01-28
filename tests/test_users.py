# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import unittest
import configparser

from ankisyncd.users import SimpleUserManager, SqliteUserManager
from ankisyncd.users import get_user_manager

import helpers.server_utils

class FakeUserManager(SimpleUserManager):
    def __init__(self, config):
        pass

class BadUserManager:
    pass

class UserManagerFactoryTest(unittest.TestCase):
    def test_get_user_manager(self):
        # Get absolute path to development ini file.
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ini_file_path = os.path.join(script_dir,
                                     "assets",
                                     "test.conf")

        # Create temporary files and dirs the server will use.
        server_paths = helpers.server_utils.create_server_paths()

        config = configparser.ConfigParser()
        config.read(ini_file_path)

        # Use custom files and dirs in settings. Should be SqliteUserManager
        config['sync_app'].update(server_paths)
        self.assertTrue(type(get_user_manager(config['sync_app']) == SqliteUserManager))

        # No value defaults to SimpleUserManager
        config.remove_option("sync_app", "auth_db_path")
        self.assertTrue(type(get_user_manager(config['sync_app'])) == SimpleUserManager)

        # A conf-specified UserManager is loaded
        config.set("sync_app", "user_manager", 'test_users.FakeUserManager')
        self.assertTrue(type(get_user_manager(config['sync_app'])) == FakeUserManager)

        # Should fail at load time if the class doesn't inherit from  SimpleUserManager
        config.set("sync_app", "user_manager", 'test_users.BadUserManager')
        with self.assertRaises(TypeError):
            um = get_user_manager(config['sync_app'])

        # Add the auth_db_path back, it should take precedence over BadUserManager
        config['sync_app'].update(server_paths)
        self.assertTrue(type(get_user_manager(config['sync_app']) == SqliteUserManager))


class SimpleUserManagerTest(unittest.TestCase):
    def setUp(self):
        self.user_manager = SimpleUserManager()

    def tearDown(self):
        self._user_manager = None

    def test_authenticate(self):
        good_test_un = 'username'
        good_test_pw = 'password'
        bad_test_un = 'notAUsername'
        bad_test_pw = 'notAPassword'

        self.assertTrue(self.user_manager.authenticate(good_test_un,
                                                       good_test_pw))
        self.assertTrue(self.user_manager.authenticate(bad_test_un,
                                                       bad_test_pw))
        self.assertTrue(self.user_manager.authenticate(good_test_un,
                                                       bad_test_pw))
        self.assertTrue(self.user_manager.authenticate(bad_test_un,
                                                       good_test_pw))

    def test_userdir(self):
        username = 'my_username'
        dirname = self.user_manager.userdir(username)
        self.assertEqual(dirname, username)


class SqliteUserManagerTest(unittest.TestCase):
    def setUp(self):
        basedir = tempfile.mkdtemp(prefix=self.__class__.__name__)
        self.basedir = basedir
        self.auth_db_path = os.path.join(basedir, "auth.db")
        self.collection_path = os.path.join(basedir, "collections")
        self.user_manager = SqliteUserManager(self.auth_db_path,
                                              self.collection_path)

    def tearDown(self):
        shutil.rmtree(self.basedir)
        self.user_manager = None

    def test_auth_db_exists(self):
        self.assertFalse(self.user_manager.auth_db_exists())

        self.user_manager.create_auth_db()
        self.assertTrue(self.user_manager.auth_db_exists())

        os.unlink(self.auth_db_path)
        self.assertFalse(self.user_manager.auth_db_exists())

    def test_user_list(self):
        username = "my_username"
        password = "my_password"
        self.user_manager.create_auth_db()

        self.assertEqual(self.user_manager.user_list(), [])

        self.user_manager.add_user(username, password)
        self.assertEqual(self.user_manager.user_list(), [username])

    def test_user_exists(self):
        username = "my_username"
        password = "my_password"
        self.user_manager.create_auth_db()
        self.user_manager.add_user(username, password)
        self.assertTrue(self.user_manager.user_exists(username))

        self.user_manager.del_user(username)
        self.assertFalse(self.user_manager.user_exists(username))

    def test_del_user(self):
        username = "my_username"
        password = "my_password"
        collection_dir_path = os.path.join(self.collection_path, username)
        self.user_manager.create_auth_db()
        self.user_manager.add_user(username, password)
        self.user_manager.del_user(username)

        # User should be gone.
        self.assertFalse(self.user_manager.user_exists(username))
        # User's collection dir should still be there.
        self.assertTrue(os.path.isdir(collection_dir_path))

    def test_add_user(self):
        username = "my_username"
        password = "my_password"
        expected_dir_path = os.path.join(self.collection_path, username)
        self.user_manager.create_auth_db()

        self.assertFalse(os.path.exists(expected_dir_path))

        self.user_manager.add_user(username, password)

        # User db entry and collection dir should be present.
        self.assertTrue(self.user_manager.user_exists(username))
        self.assertTrue(os.path.isdir(expected_dir_path))

    def test_add_users(self):
        users_data = [("my_first_username", "my_first_password"),
                      ("my_second_username", "my_second_password")]
        self.user_manager.create_auth_db()
        self.user_manager.add_users(users_data)

        user_list = self.user_manager.user_list()
        self.assertIn("my_first_username", user_list)
        self.assertIn("my_second_username", user_list)
        self.assertTrue(os.path.isdir(os.path.join(self.collection_path,
                                                   "my_first_username")))
        self.assertTrue(os.path.isdir(os.path.join(self.collection_path,
                                                   "my_second_username")))

    def test__add_user_to_auth_db(self):
        username = "my_username"
        password = "my_password"
        self.user_manager.create_auth_db()
        self.user_manager.add_user(username, password)

        self.assertTrue(self.user_manager.user_exists(username))

    def test_create_auth_db(self):
        self.assertFalse(os.path.exists(self.auth_db_path))
        self.user_manager.create_auth_db()
        self.assertTrue(os.path.isfile(self.auth_db_path))

    def test__create_user_dir(self):
        username = "my_username"
        expected_dir_path = os.path.join(self.collection_path, username)
        self.assertFalse(os.path.exists(expected_dir_path))
        self.user_manager._create_user_dir(username)
        self.assertTrue(os.path.isdir(expected_dir_path))

    def test_authenticate(self):
        username = "my_username"
        password = "my_password"

        self.user_manager.create_auth_db()
        self.user_manager.add_user(username, password)

        self.assertTrue(self.user_manager.authenticate(username,
                                                       password))

    def test_set_password_for_user(self):
        username = "my_username"
        password = "my_password"
        new_password = "my_new_password"

        self.user_manager.create_auth_db()
        self.user_manager.add_user(username, password)

        self.user_manager.set_password_for_user(username, new_password)
        self.assertFalse(self.user_manager.authenticate(username,
                                                        password))
        self.assertTrue(self.user_manager.authenticate(username,
                                                       new_password))

