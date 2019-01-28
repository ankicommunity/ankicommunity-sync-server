# -*- coding: utf-8 -*-

import os
import unittest
import configparser

from ankisyncd.collection import CollectionWrapper
from ankisyncd.collection import get_collection_wrapper

import helpers.server_utils

class FakeCollectionWrapper(CollectionWrapper):
    def __init__(self, config, path, setup_new_collection=None):
        self. _CollectionWrapper__col = None
        pass

class BadCollectionWrapper:
    pass

class CollectionWrapperFactoryTest(unittest.TestCase):
    def test_get_collection_wrapper(self):
        # Get absolute path to development ini file.
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ini_file_path = os.path.join(script_dir,
                                     "assets",
                                     "test.conf")

        # Create temporary files and dirs the server will use.
        server_paths = helpers.server_utils.create_server_paths()

        config = configparser.ConfigParser()
        config.read(ini_file_path)
        path = os.path.realpath('fake/collection.anki2')

        # Use custom files and dirs in settings. Should be CollectionWrapper
        config['sync_app'].update(server_paths)
        self.assertTrue(type(get_collection_wrapper(config['sync_app'], path) == CollectionWrapper))

        # A conf-specified CollectionWrapper is loaded
        config.set("sync_app", "collection_wrapper", 'test_collection_wrappers.FakeCollectionWrapper')
        self.assertTrue(type(get_collection_wrapper(config['sync_app'], path)) == FakeCollectionWrapper)

        # Should fail at load time if the class doesn't inherit from CollectionWrapper
        config.set("sync_app", "collection_wrapper", 'test_collection_wrappers.BadCollectionWrapper')
        with self.assertRaises(TypeError):
            pm = get_collection_wrapper(config['sync_app'], path)

