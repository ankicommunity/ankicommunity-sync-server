
import os
import shutil
import tempfile
import unittest

import AnkiServer
from AnkiServer.collection import CollectionManager
from AnkiServer.apps.rest_app import RestApp, CollectionHandlerGroup, DeckHandlerGroup

import anki
import anki.storage

class RestAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.collection_manager = CollectionManager()
        self.rest_app = RestApp(self.temp_dir, collection_manager=self.collection_manager)

    def tearDown(self):
        self.collection_manager.shutdown()
        self.collection_manager = None
        self.rest_app = None
        shutil.rmtree(self.temp_dir)

    def test_parsePath(self):
        tests = [
            ('collection/aoeu', ('collection', 'index', ['aoeu'])),
        ]

        for path, result in tests:
            self.assertEqual(self.rest_app._parsePath(path), result)

class CollectionTestBase(unittest.TestCase):
    """Parent class for tests that need a collection set up and torn down."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.collection_path = os.path.join(self.temp_dir, 'collection.anki2');
        self.collection = anki.storage.Collection(self.collection_path)

    def tearDown(self):
        self.collection.close()
        self.collection = None
        shutil.rmtree(self.temp_dir)

class CollectionHandlerGroupTest(CollectionTestBase):
    def setUp(self):
        super(CollectionHandlerGroupTest, self).setUp()
        self.handler = CollectionHandlerGroup()

    def execute(self, name, data):
        ids = ['collection_name']
        func = getattr(self.handler, name)
        return func(self.collection, data, ids)

    def test_list_decks(self):
        data = {}
        ret = self.execute('list_decks', data)

        # It contains only the 'Default' deck
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['name'], 'Default')

    def test_select_deck(self):
        data = {'deck_id': '1'}
        ret = self.execute('select_deck', data)
        self.assertEqual(ret, None);

class DeckHandlerGroupTest(CollectionTestBase):
    def setUp(self):
        super(DeckHandlerGroupTest, self).setUp()
        self.handler = DeckHandlerGroup()

    def execute(self, name, data):
        ids = ['collection_name', '1']
        func = getattr(self.handler, name)
        return func(self.collection, data, ids)

    def test_next_card(self):
        ret = self.execute('next_card', {})
        self.assertEqual(ret, None)

        # TODO: add a note programatically



if __name__ == '__main__':
    unittest.main()

