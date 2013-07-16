
import os
import shutil
import tempfile
import unittest
import logging
from pprint import pprint

import mock
from mock import MagicMock

import AnkiServer
from AnkiServer.collection import CollectionManager
from AnkiServer.apps.rest_app import RestApp, CollectionHandlerGroup, DeckHandlerGroup

from webob.exc import *

import anki
import anki.storage

class RestAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.collection_manager = CollectionManager()
        self.rest_app = RestApp(self.temp_dir, collection_manager=self.collection_manager)

        # disable all but critical errors!
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        self.collection_manager.shutdown()
        self.collection_manager = None
        self.rest_app = None
        shutil.rmtree(self.temp_dir)

    def test_parsePath(self):
        tests = [
            ('collection/user', ('collection', 'index', ['user'])),
            ('collection/user/handler', ('collection', 'handler', ['user'])),
            ('collection/user/note/123', ('note', 'index', ['user', '123'])),
            ('collection/user/note/123/handler', ('note', 'handler', ['user', '123'])),
            ('collection/user/deck/name', ('deck', 'index', ['user', 'name'])),
            ('collection/user/deck/name/handler', ('deck', 'handler', ['user', 'name'])),
            ('collection/user/deck/name/card/123', ('card', 'index', ['user', 'name', '123'])),
            ('collection/user/deck/name/card/123/handler', ('card', 'handler', ['user', 'name', '123'])),
            # the leading slash should make no difference!
            ('/collection/user', ('collection', 'index', ['user'])),
        ]

        for path, result in tests:
            self.assertEqual(self.rest_app._parsePath(path), result)

    def test_parsePath_not_found(self):
        tests = [
          'bad',
          'bad/oaeu',
          'collection',
          'collection/user/handler/bad',
          '',
          '/',
        ]

        for path in tests:
            self.assertRaises(HTTPNotFound, self.rest_app._parsePath, path)

    def test_getCollectionPath(self):
        def fullpath(collection_id):
            return os.path.normpath(os.path.join(self.temp_dir, collection_id, 'collection.anki2'))
            
        # This is simple and straight forward!
        self.assertEqual(self.rest_app._getCollectionPath('user'), fullpath('user'))

        # These are dangerous - the user is trying to hack us!
        dangerous = ['../user', '/etc/passwd', '/tmp/aBaBaB', '/root/.ssh/id_rsa']
        for collection_id in dangerous:
            self.assertRaises(HTTPBadRequest, self.rest_app._getCollectionPath, collection_id)

    def test_getHandler(self):
        def handlerOne():
            pass

        def handlerTwo():
            pass
        handlerTwo.hasReturnValue = False
        
        self.rest_app.add_handler('collection', 'handlerOne', handlerOne)
        self.rest_app.add_handler('deck', 'handlerTwo', handlerTwo)

        (handler, hasReturnValue) = self.rest_app._getHandler('collection', 'handlerOne')
        self.assertEqual(handler, handlerOne)
        self.assertEqual(hasReturnValue, True)

        (handler, hasReturnValue) = self.rest_app._getHandler('deck', 'handlerTwo')
        self.assertEqual(handler, handlerTwo)
        self.assertEqual(hasReturnValue, False)

        # try some bad handler names and types
        self.assertRaises(HTTPNotFound, self.rest_app._getHandler, 'collection', 'nonExistantHandler')
        self.assertRaises(HTTPNotFound, self.rest_app._getHandler, 'nonExistantType', 'handlerOne')

    def test_parseRequestBody(self):
        req = MagicMock()
        req.body = '{"key":"value"}'

        data = self.rest_app._parseRequestBody(req)
        self.assertEqual(data, {'key': 'value'})
        self.assertEqual(data.keys(), ['key'])
        self.assertEqual(type(data.keys()[0]), str)

        # test some bad data
        req.body = '{aaaaaaa}'
        self.assertRaises(HTTPBadRequest, self.rest_app._parseRequestBody, req)

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

    def add_note(self, data):
        from anki.notes import Note

        # TODO: we need to check the input for the correct keys.. Can we automate
        # this somehow? Maybe using KeyError or wrapper or something?

        #pprint(self.collection.models.all())
        #pprint(self.collection.models.current())

        model = self.collection.models.byName(data['model'])
        #pprint (self.collection.models.fieldNames(model))

        note = Note(self.collection, model)
        for name, value in data['fields'].items():
            note[name] = value

        if data.has_key('tags'):
            note.setTagsFromStr(data['tags'])

        ret = self.collection.addNote(note)

    def find_notes(self, data):
        query = data.get('query', '')
        ids = self.collection.getNotes(query)


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

        # add a note programatically
        note = {
            'model': 'Basic',
            'fields': {
                'Front': 'The front',
                'Back': 'The back',
            },
            'tags': "Tag1 Tag2",
        }
        self.add_note(note)

        # get the id for the one card on this collection
        card_id = self.collection.findCards('')[0]

        self.collection.sched.reset()
        ret = self.execute('next_card', {})
        self.assertEqual(ret['id'], card_id)

if __name__ == '__main__':
    unittest.main()

