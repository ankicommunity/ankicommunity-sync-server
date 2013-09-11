
# AnkiServer - A personal Anki sync server
# Copyright (C) 2013 David Snopek
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from anki.importing.csvfile import TextImporter
from anki.importing.apkg import AnkiPackageImporter
from anki.importing.anki1 import Anki1Importer
from anki.importing.supermemo_xml import SupermemoXmlImporter
from anki.importing.mnemo import MnemosyneImporter
from anki.importing.pauker import PaukerImporter

__all__ = ['get_importer_class', 'import_file']

importers = {
  'text': TextImporter,
  'apkg': AnkiPackageImporter,
  'anki1': Anki1Importer,
  'supermemo_xml': SupermemoXmlImporter,
  'mnemosyne': MnemosyneImporter,
  'pauker': PaukerImporter,
}

def get_importer_class(type):
    global importers
    return importers.get(type)

def import_file(importer_class, col, path, allow_update = False):
    importer = importer_class(col, path)

    if allow_update:
        importer.allowUpdate = True

    if importer.needMapper:
        importer.open()

    importer.run()

#
# Monkey patch anki.importing.anki2 to support updating existing notes.
# TODO: submit a patch to Anki!
#

def _importNotes(self):
    # build guid -> (id,mod,mid) hash & map of existing note ids
    self._notes = {}
    existing = {}
    for id, guid, mod, mid in self.dst.db.execute(
        "select id, guid, mod, mid from notes"):
        self._notes[guid] = (id, mod, mid)
        existing[id] = True
    # we may need to rewrite the guid if the model schemas don't match,
    # so we need to keep track of the changes for the card import stage
    self._changedGuids = {}
    # iterate over source collection
    add = []
    dirty = []
    usn = self.dst.usn()
    dupes = 0
    for note in self.src.db.execute(
        "select * from notes"):
        # turn the db result into a mutable list
        note = list(note)
        shouldAdd = self._uniquifyNote(note)
        if shouldAdd:
            # ensure id is unique
            while note[0] in existing:
                note[0] += 999
            existing[note[0]] = True
            # bump usn
            note[4] = usn
            # update media references in case of dupes
            note[6] = self._mungeMedia(note[MID], note[6])
            add.append(note)
            dirty.append(note[0])
            # note we have the added the guid
            self._notes[note[GUID]] = (note[0], note[3], note[MID])
        else:
            dupes += 1

            # update existing note
            newer = note[3] > mod
            if self.allowUpdate and self._mid(mid) == mid and newer:
                localNid = self._notes[note[GUID]][0]
                note[0] = localNid
                note[4] = usn
                add.append(note)
                dirty.append(note[0])

    if dupes:
        self.log.append(_("Already in collection: %s.") % (ngettext(
            "%d note", "%d notes", dupes) % dupes))
    # add to col
    self.dst.db.executemany(
        "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)",
        add)
    self.dst.updateFieldCache(dirty)
    self.dst.tags.registerNotes(dirty)

from anki.importing.anki2 import Anki2Importer, MID, GUID
from anki.lang import _, ngettext
Anki2Importer._importNotes = _importNotes
Anki2Importer.allowUpdate = False

