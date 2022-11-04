# -*- coding: utf-8 -*-
import unittest
import tempfile
import os
from unittest.mock import MagicMock
import shutil

import anki
import anki.storage

from ankisyncd.collection import CollectionManager


class CollectionTestBase(unittest.TestCase):
    """Parent class for tests that need a collection set up and torn down."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.collection_path = os.path.join(self.temp_dir, "collection.anki2")
        cm = CollectionManager({})
        collectionWrapper = cm.get_collection(self.collection_path)
        self.collection = collectionWrapper._get_collection()
        self.mock_app = MagicMock()

    def tearDown(self):
        self.collection.close()
        self.collection = None
        shutil.rmtree(self.temp_dir)
        self.mock_app.reset_mock()

    # TODO: refactor into some kind of utility
    def add_note(self, data):
        from anki.notes import Note

        model = self.collection.models.byName(data["model"])

        note = Note(self.collection, model)
        for name, value in data["fields"].items():
            note[name] = value

        if "tags" in data:
            note.setTagsFromStr(data["tags"])

        self.collection.addNote(note)

    # TODO: refactor into a parent class
    def add_default_note(self, count=1):
        data = {
            "model": "Basic",
            "fields": {
                "Front": "The front",
                "Back": "The back",
            },
            "tags": "Tag1 Tag2",
        }
        for idx in range(0, count):
            self.add_note(data)
