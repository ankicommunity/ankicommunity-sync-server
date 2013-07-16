
from anki.importing.csvfile import TextImporter
from anki.importing.apkg import AnkiPackageImporter
from anki.importing.anki1 import Anki1Importer
from anki.importing.supermemo_xml import SupermemoXmlImporter
from anki.importing.mnemo import MnemosyneImporter
from anki.importing.pauker import PaukerImporter

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

def import_file(importer_class, col, path):
    importer = importer_class(col, path)

    if importer.needMapper:
        importer.open()

    importer.run()

