
import os
import shutil
import tempfile
import unittest

import mock
from mock import MagicMock, sentinel

import AnkiServer
from AnkiServer.importer import get_importer_class, import_file

import anki.storage

# TODO: refactor into some kind of utility
def add_note(col, data):
    from anki.notes import Note

    model = col.models.byName(data['model'])

    note = Note(col, model)
    for name, value in data['fields'].items():
        note[name] = value

    if data.has_key('tags'):
        note.setTagsFromStr(data['tags'])

    col.addNote(note)

class ImporterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.collection_path = os.path.join(self.temp_dir, 'collection.anki2')
        self.collection = anki.storage.Collection(self.collection_path)

    def tearDown(self):
        self.collection.close()
        self.collection = None
        shutil.rmtree(self.temp_dir)
 

    # TODO: refactor into a parent class
    def add_default_note(self, count=1):
        data = {
            'model': 'Basic',
            'fields': {
                'Front': 'The front',
                'Back': 'The back',
            },
            'tags': "Tag1 Tag2",
        }
        for idx in range(0, count):
            add_note(self.collection, data)
            self.add_note(data)

    def test_resync(self):
        from anki.exporting import AnkiPackageExporter
        from anki.utils import intTime

        # create a new collection with a single note
        src_collection = anki.storage.Collection(os.path.join(self.temp_dir, 'src_collection.anki2'))
        add_note(src_collection, {
            'model': 'Basic',
            'fields': {
              'Front': 'The front',
              'Back': 'The back',
            },
            'tags': 'Tag1 Tag2',
        })
        note_id = src_collection.findNotes('')[0]
        note = src_collection.getNote(note_id)
        self.assertEqual(note.id, note_id)
        self.assertEqual(note['Front'], 'The front')
        self.assertEqual(note['Back'], 'The back')

        # export to an .apkg file
        dst1_path = os.path.join(self.temp_dir, 'export1.apkg')
        exporter = AnkiPackageExporter(src_collection)
        exporter.exportInto(dst1_path)

        # import it into the main collection
        import_file(get_importer_class('apkg'), self.collection, dst1_path)

        # make sure the note exists
        note = self.collection.getNote(note_id)
        self.assertEqual(note.id, note_id)
        self.assertEqual(note['Front'], 'The front')
        self.assertEqual(note['Back'], 'The back')

        # now we change the source collection and re-export it
        note = src_collection.getNote(note_id)
        note['Front'] = 'The new front'
        note.tags.append('Tag3')
        note.flush(intTime()+1)
        dst2_path = os.path.join(self.temp_dir, 'export2.apkg')
        exporter = AnkiPackageExporter(src_collection)
        exporter.exportInto(dst2_path)

        # first, import it without allow_update - no change should happen
        import_file(get_importer_class('apkg'), self.collection, dst2_path, allow_update=False)
        note = self.collection.getNote(note_id)
        self.assertEqual(note['Front'], 'The front')
        self.assertEqual(note.tags, ['Tag1', 'Tag2'])

        # now, import it with allow_update=True, so the note should change
        import_file(get_importer_class('apkg'), self.collection, dst2_path, allow_update=True)
        note = self.collection.getNote(note_id)
        self.assertEqual(note['Front'], 'The new front')
        self.assertEqual(note.tags, ['Tag1', 'Tag2', 'Tag3'])

if __name__ == '__main__':
    unittest.main()

