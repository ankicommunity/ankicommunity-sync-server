
import os
import shutil
import tempfile
import unittest

import mock
from mock import MagicMock, sentinel

import AnkiServer
from AnkiServer.collection import CollectionWrapper, CollectionManager

class CollectionWrapperTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.collection_path = os.path.join(self.temp_dir, 'collection.anki2');

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_lifecycle_real(self):
        """Testing common life-cycle with existing and non-existant collections. This
        test uses the real Anki objects and actually creates a new collection on disk."""

        wrapper = CollectionWrapper(self.collection_path)
        self.assertFalse(os.path.exists(self.collection_path))
        self.assertFalse(wrapper.opened())

        wrapper.open()
        self.assertTrue(os.path.exists(self.collection_path))
        self.assertTrue(wrapper.opened())

        # calling open twice shouldn't break anything
        wrapper.open()

        wrapper.close()
        self.assertTrue(os.path.exists(self.collection_path))
        self.assertFalse(wrapper.opened())

        # open the same collection again (not a creation)
        wrapper = CollectionWrapper(self.collection_path)
        self.assertFalse(wrapper.opened())
        wrapper.open()
        self.assertTrue(wrapper.opened())
        wrapper.close()
        self.assertFalse(wrapper.opened())
        self.assertTrue(os.path.exists(self.collection_path))

    def test_del(self):
        with mock.patch('anki.storage.Collection') as anki_storage_Collection:
            col = anki_storage_Collection.return_value
            wrapper = CollectionWrapper(self.collection_path)
            wrapper.open()
            wrapper = None
            col.close.assert_called_with()

    def test_setup_func(self):
        # Run it when the collection doesn't exist
        with mock.patch('anki.storage.Collection') as anki_storage_Collection:
            col = anki_storage_Collection.return_value
            setup_new_collection = MagicMock()
            self.assertFalse(os.path.exists(self.collection_path))
            wrapper = CollectionWrapper(self.collection_path, setup_new_collection)
            wrapper.open()
            anki_storage_Collection.assert_called_with(self.collection_path)
            setup_new_collection.assert_called_with(col)
            wrapper = None

        # Make sure that no collection was actually created
        self.assertFalse(os.path.exists(self.collection_path))
        
        # Create a faux collection file
        with file(self.collection_path, 'wt') as fd:
            fd.write('Collection!')

        # Run it when the collection does exist
        with mock.patch('anki.storage.Collection'):
            setup_new_collection = lambda col: self.fail("Setup function called when collection already exists!")
            self.assertTrue(os.path.exists(self.collection_path))
            wrapper = CollectionWrapper(self.collection_path, setup_new_collection)
            wrapper.open()
            anki_storage_Collection.assert_called_with(self.collection_path)
            wrapper = None

    def test_execute(self):
        with mock.patch('anki.storage.Collection') as anki_storage_Collection:
            col = anki_storage_Collection.return_value
            func = MagicMock()
            func.return_value = sentinel.some_object

            # check that execute works and auto-creates the collection
            wrapper = CollectionWrapper(self.collection_path)
            ret = wrapper.execute(func, [1, 2, 3], {'key': 'aoeu'})
            self.assertEqual(ret, sentinel.some_object)
            anki_storage_Collection.assert_called_with(self.collection_path)
            func.assert_called_with(col, 1, 2, 3, key='aoeu')

            # check that execute always returns False if waitForReturn=False
            func.reset_mock()
            ret = wrapper.execute(func, [1, 2, 3], {'key': 'aoeu'}, waitForReturn=False)
            self.assertEqual(ret, None)
            func.assert_called_with(col, 1, 2, 3, key='aoeu')

class CollectionManagerTest(unittest.TestCase):
    def test_lifecycle(self):
        with mock.patch('AnkiServer.collection.CollectionManager.collection_wrapper') as CollectionWrapper:
            wrapper = MagicMock()
            CollectionWrapper.return_value = wrapper

            manager = CollectionManager()

            # check getting a new collection
            ret = manager.get_collection('path1')
            CollectionWrapper.assert_called_with(os.path.realpath('path1'), None)
            self.assertEqual(ret, wrapper)

            # change the return value, so that it would return a new object
            new_wrapper = MagicMock()
            CollectionWrapper.return_value = new_wrapper
            CollectionWrapper.reset_mock()

            # get the new wrapper
            ret = manager.get_collection('path2')
            CollectionWrapper.assert_called_with(os.path.realpath('path2'), None)
            self.assertEqual(ret, new_wrapper)

            # make sure the wrapper and new_wrapper are different
            self.assertNotEqual(wrapper, new_wrapper)

            # assert that calling with the first path again, returns the first wrapper
            ret = manager.get_collection('path1')
            self.assertEqual(ret, wrapper)

            manager.shutdown()
            wrapper.close.assert_called_with()
            new_wrapper.close.assert_called_with()

if __name__ == '__main__':
    unittest.main()

