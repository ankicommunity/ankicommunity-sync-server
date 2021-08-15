# ankisyncd - A personal Anki sync server
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

import gzip
import hashlib
import io
import json
import logging
import os
import random
import re
import string
import sys
import time
import unicodedata
import zipfile
from configparser import ConfigParser
from sqlite3 import dbapi2 as sqlite

from webob import Response
from webob.dec import wsgify
from webob.exc import *

import anki.db
import anki.utils
from anki.consts import REM_CARD, REM_NOTE

from ankisyncd.full_sync import get_full_sync_manager
from ankisyncd.sessions import get_session_manager
from ankisyncd.sync import Syncer, SYNC_VER, SYNC_ZIP_SIZE, SYNC_ZIP_COUNT
from ankisyncd.users import get_user_manager

logger = logging.getLogger("ankisyncd")


class SyncCollectionHandler(Syncer):
    operations = ['meta', 'applyChanges', 'start', 'applyGraves', 'chunk', 'applyChunk', 'sanityCheck2', 'finish']

    def __init__(self, col, session):
        # So that 'server' (the 3rd argument) can't get set
        super().__init__(col)
        self.session = session

    @staticmethod
    def _old_client(cv):
        if not cv:
            return False

        note = {"alpha": 0, "beta": 0, "rc": 0}
        client, version, platform = cv.split(',')

        if 'arch' not in version:
            for name in note.keys():
                if name in version:
                    vs = version.split(name)
                    version = vs[0]
                    note[name] = int(vs[-1])

        # convert the version string, ignoring non-numeric suffixes like in beta versions of Anki
        version_nosuffix = re.sub(r'[^0-9.].*$', '', version)
        version_int = [int(x) for x in version_nosuffix.split('.')]

        if client == 'ankidesktop':
            return version_int < [2, 0, 27]
        elif client == 'ankidroid':
            if version_int == [2, 3]:
               if note["alpha"]:
                  return note["alpha"] < 4
            else:
               return version_int < [2, 2, 3]
        else:  # unknown client, assume current version
            return False

    def meta(self, v=None, cv=None):
        if self._old_client(cv):
            return Response(status=501)  # client needs upgrade
        if v > SYNC_VER:
            return {"cont": False, "msg": "Your client is using unsupported sync protocol ({}, supported version: {})".format(v, SYNC_VER)}
        if v < 9 and self.col.schedVer() >= 2:
            return {"cont": False, "msg": "Your client doesn't support the v{} scheduler.".format(self.col.schedVer())}

        # Make sure the media database is open!
        self.col.media.connect()

        return {
            'mod': self.col.mod,
            'scm': self.col.scm,
            'usn': self.col._usn,
            'ts': anki.utils.intTime(),
            'musn': self.col.media.lastUsn(),
            'uname': self.session.name,
            'msg': '',
            'cont': True,
            'hostNum': 0,
        }

    def usnLim(self):
        return "usn >= %d" % self.minUsn

    # ankidesktop >=2.1rc2 sends graves in applyGraves, but still expects
    # server-side deletions to be returned by start
    def start(self, minUsn, lnewer, graves={"cards": [], "notes": [], "decks": []}, offset=None):
        # The offset para is passed  by client V2 scheduler,which is minutes_west.
        # Since now have not thorougly test the V2 scheduler, we leave this comments here, and 
        # just enable the V2 scheduler in the serve code.    

        self.maxUsn = self.col._usn
        self.minUsn = minUsn
        self.lnewer = not lnewer
        lgraves = self.removed()
        # convert grave:None to {'cards': [], 'notes': [], 'decks': []}
        #     because req.POST['data'] returned value of grave is None     
        if graves==None:
            graves={'cards': [], 'notes': [], 'decks': []}
        self.remove(graves)
        return lgraves

    def applyGraves(self, chunk):
        self.remove(chunk)

    def applyChanges(self, changes):
        self.rchg = changes
        lchg = self.changes()
        # merge our side before returning
        self.mergeChanges(lchg, self.rchg)
        return lchg

    def sanityCheck2(self, client, full=None):
        server = self.sanityCheck(full)
        if client != server:
            logger.info(
                f"sanity check failed with server: {server} client: {client}"
            )

            return dict(status="bad", c=client, s=server)
        return dict(status="ok")

    def finish(self, mod=None):
        return super().finish(anki.utils.intTime(1000))

    # This function had to be put here in its entirety because Syncer.removed()
    # doesn't use self.usnLim() (which we override in this class) in queries.
    # "usn=-1" has been replaced with "usn >= ?", self.minUsn by hand.
    def removed(self):
        cards = []
        notes = []
        decks = []

        curs = self.col.db.execute(
            "select oid, type from graves where usn >= ?", self.minUsn)

        for oid, type in curs:
            if type == REM_CARD:
                cards.append(oid)
            elif type == REM_NOTE:
                notes.append(oid)
            else:
                decks.append(oid)

        return dict(cards=cards, notes=notes, decks=decks)

    def getModels(self):
        return [m for m in self.col.models.all() if m['usn'] >= self.minUsn]

    def getDecks(self):
        return [
            [g for g in self.col.decks.all() if g['usn'] >= self.minUsn],
            [g for g in self.col.decks.allConf() if g['usn'] >= self.minUsn]
        ]

    def getTags(self):
        return [t for t, usn in self.allItems()
                if usn >= self.minUsn]

class SyncMediaHandler:
    operations = ['begin', 'mediaChanges', 'mediaSanity', 'uploadChanges', 'downloadFiles']

    def __init__(self, col, session):
        self.col = col
        self.session = session

    def begin(self, skey):
        return {
            'data': {
                'sk': skey,
                'usn': self.col.media.lastUsn(),
            },
            'err': '',
        }

    def uploadChanges(self, data):
        """
        The zip file contains files the client hasn't synced with the server
        yet ('dirty'), and info on files it has deleted from its own media dir.
        """

        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            self._check_zip_data(z)
            processed_count = self._adopt_media_changes_from_zip(z)

        return {
            'data': [processed_count, self.col.media.lastUsn()],
            'err': '',
        }

    @staticmethod
    def _check_zip_data(zip_file):
        max_zip_size = 100*1024*1024
        max_meta_file_size = 100000

        meta_file_size = zip_file.getinfo("_meta").file_size
        sum_file_sizes = sum(info.file_size for info in zip_file.infolist())

        if meta_file_size > max_meta_file_size:
            raise ValueError("Zip file's metadata file is larger than %s "
                             "Bytes." % max_meta_file_size)
        elif sum_file_sizes > max_zip_size:
            raise ValueError("Zip file contents are larger than %s Bytes." %
                             max_zip_size)

    def _adopt_media_changes_from_zip(self, zip_file):
        """
        Adds and removes files to/from the database and media directory
        according to the data in zip file zipData.
        """

        # Get meta info first.
        meta = json.loads(zip_file.read("_meta").decode())

        # Remove media files that were removed on the client.
        media_to_remove = []
        for normname, ordinal in meta:
            if not ordinal:
                media_to_remove.append(self._normalize_filename(normname))

        # Add media files that were added on the client.
        media_to_add = []
        usn = self.col.media.lastUsn()
        oldUsn = usn
        media_dir = self.col.media.dir()
        os.makedirs(media_dir, exist_ok=True)

        for i in zip_file.infolist():
            if i.filename == "_meta":  # Ignore previously retrieved metadata.
                continue

            file_data = zip_file.read(i)
            csum = anki.utils.checksum(file_data)
            filename = self._normalize_filename(meta[int(i.filename)][0])
            file_path = os.path.join(media_dir, filename)

            # Save file to media directory.
            with open(file_path, 'wb') as f:
                f.write(file_data)

            usn += 1
            media_to_add.append((filename, usn, csum))

        # We count all files we are to remove, even if we don't have them in
        # our media directory and our db doesn't know about them.
        processed_count = len(media_to_remove) + len(media_to_add)

        assert len(meta) == processed_count  # sanity check

        if media_to_remove:
            self._remove_media_files(media_to_remove)

        if media_to_add:
            self.col.media.addMedia(media_to_add)

        assert self.col.media.lastUsn() == oldUsn + processed_count  # TODO: move to some unit test
        return processed_count

    @staticmethod
    def _normalize_filename(filename):
        """
        Performs unicode normalization for file names. Logic taken from Anki's
        MediaManager.addFilesFromZip().
        """

        # Normalize name for platform.
        if anki.utils.isMac:  # global
            filename = unicodedata.normalize("NFD", filename)
        else:
            filename = unicodedata.normalize("NFC", filename)

        return filename

    def _remove_media_files(self, filenames):
        """
        Marks all files in list filenames as deleted and removes them from the
        media directory.
        """
        logger.debug('Removing %d files from media dir.' % len(filenames))
        for filename in filenames:
            try:
                self.col.media.syncDelete(filename)
            except OSError as err:
                logger.error("Error when removing file '%s' from media dir: "
                              "%s" % (filename, str(err)))

    def downloadFiles(self, files):
        flist = {}
        cnt = 0
        sz = 0
        f = io.BytesIO()

        with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for fname in files:
                z.write(os.path.join(self.col.media.dir(), fname), str(cnt))
                flist[str(cnt)] = fname
                sz += os.path.getsize(os.path.join(self.col.media.dir(), fname))
                if sz > SYNC_ZIP_SIZE or cnt > SYNC_ZIP_COUNT:
                    break
                cnt += 1

            z.writestr("_meta", json.dumps(flist))

        return f.getvalue()

    def mediaChanges(self, lastUsn):
        result = []
        server_lastUsn = self.col.media.lastUsn()

        if lastUsn < server_lastUsn or lastUsn == 0:
            for fname,usn,csum, in self.col.media.changes(lastUsn):
                result.append([fname, usn, csum])

        # anki assumes server_lastUsn == result[-1][1]
        # ref: anki/sync.py:720 (commit cca3fcb2418880d0430a5c5c2e6b81ba260065b7)
        result.reverse()

        return {'data': result, 'err': ''}

    def mediaSanity(self, local=None):
        if self.col.media.mediaCount() == local:
            result = "OK"
        else:
            result = "FAILED"

        return {'data': result, 'err': ''}

class SyncUserSession:
    def __init__(self, name, path, collection_manager, setup_new_collection=None):
        self.skey = self._generate_session_key()
        self.name = name
        self.path = path
        self.collection_manager = collection_manager
        self.setup_new_collection = setup_new_collection
        self.version = None
        self.client_version = None
        self.created = time.time()
        self.collection_handler = None
        self.media_handler = None

        # make sure the user path exists
        if not os.path.exists(path):
            os.mkdir(path)

    def _generate_session_key(self):
        return anki.utils.checksum(str(random.random()))[:8]

    def get_collection_path(self):
        return os.path.realpath(os.path.join(self.path, 'collection.anki2'))

    def get_thread(self):
        return self.collection_manager.get_collection(self.get_collection_path(), self.setup_new_collection)

    def get_handler_for_operation(self, operation, col):
        if operation in SyncCollectionHandler.operations:
            attr, handler_class = 'collection_handler', SyncCollectionHandler
        elif operation in SyncMediaHandler.operations:
            attr, handler_class = 'media_handler', SyncMediaHandler
        else:
            raise Exception("no handler for {}".format(operation))

        if getattr(self, attr) is None:
            setattr(self, attr, handler_class(col, self))
        handler = getattr(self, attr)
        # The col object may actually be new now! This happens when we close a collection
        # for inactivity and then later re-open it (creating a new Collection object).
        handler.col = col
        return handler

class SyncApp:
    valid_urls = SyncCollectionHandler.operations + SyncMediaHandler.operations + ['hostKey', 'upload', 'download']

    def __init__(self, config):
        from ankisyncd.thread import get_collection_manager

        self.data_root = os.path.abspath(config['data_root'])
        self.base_url  = config['base_url']
        self.base_media_url  = config['base_media_url']
        self.setup_new_collection = None

        self.user_manager = get_user_manager(config)
        self.session_manager = get_session_manager(config)
        self.full_sync_manager = get_full_sync_manager(config)
        self.collection_manager = get_collection_manager(config)

        # make sure the base_url has a trailing slash
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        if not self.base_media_url.endswith('/'):
            self.base_media_url += '/'

    def generateHostKey(self, username):
        """Generates a new host key to be used by the given username to identify their session.
        This values is random."""

        import hashlib, time, random, string
        chars = string.ascii_letters + string.digits
        val = ':'.join([username, str(int(time.time())), ''.join(random.choice(chars) for x in range(8))]).encode()
        return hashlib.md5(val).hexdigest()

    def create_session(self, username, user_path):
        return SyncUserSession(username, user_path, self.collection_manager, self.setup_new_collection)

    def _decode_data(self, data, compression=0):
        if compression:
            with gzip.GzipFile(mode="rb", fileobj=io.BytesIO(data)) as gz:
                data = gz.read()

        try:
            data = json.loads(data.decode())
        except (ValueError, UnicodeDecodeError):
            data = {'data': data}

        return data

    def operation_hostKey(self, username, password):
        if not self.user_manager.authenticate(username, password):
            return

        dirname = self.user_manager.userdir(username)
        if dirname is None:
            return

        hkey = self.generateHostKey(username)
        user_path = os.path.join(self.data_root, dirname)
        session = self.create_session(username, user_path)
        self.session_manager.save(hkey, session)

        return {'key': hkey}

    def operation_upload(self, col, data, session):
        # Verify integrity of the received database file before replacing our
        # existing db.

        return self.full_sync_manager.upload(col, data, session)

    def operation_download(self, col, session):
        # returns user data (not media) as a sqlite3 database for replacing their
        # local copy in Anki
        return self.full_sync_manager.download(col, session)

    @wsgify
    def __call__(self, req):
        # Get and verify the session
        try:
            hkey = req.params['k']
        except KeyError:
            hkey = None

        session = self.session_manager.load(hkey, self.create_session)

        if session is None:
            try:
                skey = req.POST['sk']
                session = self.session_manager.load_from_skey(skey, self.create_session)
            except KeyError:
                skey = None

        try:
            compression = int(req.POST['c'])
        except KeyError:
            compression = 0

        try:
            data = req.POST['data'].file.read()
            data = self._decode_data(data, compression)
        except KeyError:
            data = {}

        if req.path.startswith(self.base_url):
            url = req.path[len(self.base_url):]
            if url not in self.valid_urls:
                raise HTTPNotFound()

            if url == 'hostKey':
                result = self.operation_hostKey(data.get("u"), data.get("p"))
                if result:
                    return json.dumps(result)
                else:
                    # TODO: do I have to pass 'null' for the client to receive None?
                    raise HTTPForbidden('null')

            if session is None:
                raise HTTPForbidden()

            if url in SyncCollectionHandler.operations + SyncMediaHandler.operations:
                # 'meta' passes the SYNC_VER but it isn't used in the handler
                if url == 'meta':
                    if session.skey == None and 's' in req.POST:
                        session.skey = req.POST['s']
                    if 'v' in data:
                        session.version = data['v']
                    if 'cv' in data:
                        session.client_version = data['cv']

                    self.session_manager.save(hkey, session)
                    session = self.session_manager.load(hkey, self.create_session)
                thread = session.get_thread()
                result = self._execute_handler_method_in_thread(url, data, session)
                # If it's a complex data type, we convert it to JSON
                if type(result) not in (str, bytes, Response):
                    result = json.dumps(result)

                return result

            elif url == 'upload':
                thread = session.get_thread()
                result = thread.execute(self.operation_upload, [data['data'], session])
                return result

            elif url == 'download':
                thread = session.get_thread()
                result = thread.execute(self.operation_download, [session])
                return result

            # This was one of our operations but it didn't get handled... Oops!
            raise HTTPInternalServerError()

        # media sync
        elif req.path.startswith(self.base_media_url):
            if session is None:
                raise HTTPForbidden()

            url = req.path[len(self.base_media_url):]

            if url not in self.valid_urls:
                raise HTTPNotFound()

            if url == "begin":
                data['skey'] = session.skey

            result = self._execute_handler_method_in_thread(url, data, session)

            # If it's a complex data type, we convert it to JSON
            if type(result) not in (str, bytes):
                result = json.dumps(result)

            return result

        return "Anki Sync Server"

    @staticmethod
    def _execute_handler_method_in_thread(method_name, keyword_args, session):
        """
        Gets and runs the handler method specified by method_name inside the
        thread for session. The handler method will access the collection as
        self.col.
        """

        def run_func(col, **keyword_args):
            # Retrieve the correct handler method.
            handler = session.get_handler_for_operation(method_name, col)
            handler_method = getattr(handler, method_name)

            res = handler_method(**keyword_args)

            col.save()
            return res

        run_func.__name__ = method_name  # More useful debugging messages.

        # Send the closure to the thread for execution.
        thread = session.get_thread()
        result = thread.execute(run_func, kw=keyword_args)

        return result


def make_app(global_conf, **local_conf):
    return SyncApp(**local_conf)

def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s]:%(levelname)s:%(name)s:%(message)s")
    import ankisyncd
    logger.info("ankisyncd {} ({})".format(ankisyncd._get_version(), ankisyncd._homepage))
    from wsgiref.simple_server import make_server, WSGIRequestHandler
    from ankisyncd.thread import shutdown
    import ankisyncd.config

    class RequestHandler(WSGIRequestHandler):
        logger = logging.getLogger("ankisyncd.http")

        def log_error(self, format, *args):
            self.logger.error("%s %s", self.address_string(), format%args)

        def log_message(self, format, *args):
            self.logger.info("%s %s", self.address_string(), format%args)

    if len(sys.argv) > 1:
        # backwards compat
        config = ankisyncd.config.load(sys.argv[1])
    else:
        config = ankisyncd.config.load()

    ankiserver = SyncApp(config)
    httpd = make_server(config['host'], int(config['port']), ankiserver, handler_class=RequestHandler)

    try:
        logger.info("Serving HTTP on {} port {}...".format(*httpd.server_address))
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Exiting...")
    finally:
        shutdown()

if __name__ == '__main__': main()
