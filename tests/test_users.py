# -*- coding: utf-8 -*-


import os
import unittest


from ankisyncd.users import UserManager
from helpers.file_utils import FileUtils


class SimpleUserManagerTest(unittest.TestCase):
    _good_test_un = 'username'
    _good_test_pw = 'password'

    _bad_test_un = 'notAUsername'
    _bad_test_pw = 'notAPassword'

    @classmethod
    def setUpClass(cls):
        cls.fileutils = FileUtils()

    @classmethod
    def tearDownClass(cls):
        cls.fileutils.clean_up()
        cls.fileutils = None

    def setUp(self):
        self.auth_db_path = self.fileutils.create_file_path(suffix='auth.db')
        self.collection_path = self.fileutils.create_dir_path()
        self.user_manager = UserManager(self.auth_db_path,
                                        self.collection_path)

    def tearDown(self):
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


if __name__ == '__main__':
    unittest.main()
