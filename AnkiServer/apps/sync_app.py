
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

from webob.dec import wsgify
from webob.exc import *
from webob import Response

import os
import hashlib
import logging
import random
import string
import unicodedata
import zipfile

import AnkiServer

import anki
from anki.db import DB
from anki.sync import Syncer, MediaSyncer
from anki.utils import intTime, checksum, isMac
from anki.consts import SYNC_ZIP_SIZE, SYNC_ZIP_COUNT

try:
    import simplejson as json
except ImportError:
    import json

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    from pysqlite2 import dbapi2 as sqlite
except ImportError:
    from sqlite3 import dbapi2 as sqlite

class SyncCollectionHandler(Syncer):
    operations = ['meta', 'applyChanges', 'start', 'chunk', 'applyChunk', 'sanityCheck2', 'finish']

    def __init__(self, col):
        # So that 'server' (the 3rd argument) can't get set
        Syncer.__init__(self, col)

    def meta(self, cv=None):
        # Make sure the media database is open!
        if self.col.media.db is None:
            self.col.media.connect()

        if cv is not None:
            client, version, platform = cv.split(',')
        else:
            client = 'ankidesktop'
            version = '2.0.12'
            platform = 'unknown'

        version_int = [ int(str(x).translate(None, string.ascii_letters))
                        for x in version.split('.') ]

        # Some insanity added in Anki 2.0.13
        if (client == 'ankidroid' and version_int[0] >=2 and version_int[1] >= 3) \
        or (client == 'ankidesktop' and version_int[0] >= 2 and version_int[1] >= 0 and version_int[2] >= 13):
            return {
              'scm': self.col.scm,
              'ts': intTime(),
              'mod': self.col.mod,
              'usn': self.col._usn,
              'musn': self.col.media.lastUsn(),
              'msg': '',
              'cont': True,
            }
        else:
            return (self.col.mod, self.col.scm, self.col._usn, intTime(), self.col.media.lastUsn())

class SyncMediaHandler(MediaSyncer):
    operations = ['begin', 'mediaChanges', 'mediaSanity', 'mediaList', 'uploadChanges', 'downloadFiles']

    def __init__(self, col):
        MediaSyncer.__init__(self, col)

    def begin(self, skey):
        return json.dumps({
            'data':{
                'sk':skey,
                'usn':self.col.media.lastUsn()
            },
            'err':''
        })

    def uploadChanges(self, data, skey):
        """
        The zip file contains files the client hasn't synced with the server
        yet ('dirty'), and info on files it has deleted from its own media dir.
        """

        self._check_zip_data(data)

        processed_count = self._adopt_media_changes_from_zip(data)

        # We increment our lastUsn once for each file we processed.
        # (lastUsn - processed_count) must equal the client's lastUsn.
        our_last_usn = self.col.media.lastUsn()
        self.col.media.setLastUsn(our_last_usn + processed_count)

        return json.dumps(
            {
                'data': [processed_count,
                         self.col.media.lastUsn()],
                'err': ''
            }
        )

    @staticmethod
    def _check_zip_data(zip_data):
        max_zip_size = 100*1024*1024
        max_meta_file_size = 100000

        file_buffer = StringIO(zip_data)
        zip_file = zipfile.ZipFile(file_buffer, 'r')

        meta_file_size = zip_file.getinfo("_meta").file_size
        sum_file_sizes = sum(info.file_size for info in zip_file.infolist())

        zip_file.close()
        file_buffer.close()

        if meta_file_size > max_meta_file_size:
            raise ValueError("Zip file's metadata file is larger than %s "
                             "Bytes." % max_meta_file_size)
        elif sum_file_sizes > max_zip_size:
            raise ValueError("Zip file contents are larger than %s Bytes." %
                             max_zip_size)

    def _adopt_media_changes_from_zip(self, zip_data):
        """
        Adds and removes files to/from the database and media directory
        according to the data in zip file zipData.
        """

        file_buffer = StringIO(zip_data)
        zip_file = zipfile.ZipFile(file_buffer, 'r')

        # Get meta info first.
        meta = json.loads(zip_file.read("_meta"))

        # Remove media files that were removed on the client.
        media_to_remove = []
        for normname, ordinal in meta:
            if ordinal == '':
                media_to_remove.append(self._normalize_filename(normname))

        # Add media files that were added on the client.
        media_to_add = []
        for i in zip_file.infolist():
            if i.filename == "_meta":  # Ignore previously retrieved metadata.
                continue
            else:
                file_data = zip_file.read(i)
                csum = checksum(file_data)
                filename = self._normalize_filename(meta[int(i.filename)][0])
                file_path = os.path.join(self.col.media.dir(), filename)

                # Save file to media directory.
                open(file_path, 'wb').write(file_data)
                mtime = self.col.media._mtime(file_path)

                media_to_add.append((filename, csum, mtime, 0))

        # We count all files we are to remove, even if we don't have them in
        # our media directory and our db doesn't know about them.
        processed_count = len(media_to_remove) + len(media_to_add)

        assert len(meta) == processed_count  # sanity check

        if media_to_remove:
            self._remove_media_files(media_to_remove)

        if media_to_add:
            self.col.media.db.executemany(
                "INSERT OR REPLACE INTO media VALUES (?,?,?,?)", media_to_add)

        return processed_count

    @staticmethod
    def _normalize_filename(filename):
        """
        Performs unicode normalization for file names. Logic taken from Anki's
        MediaManager.addFilesFromZip().
        """

        if not isinstance(filename, unicode):
            filename = unicode(filename, "utf8")

        # Normalize name for platform.
        if isMac:  # global
            filename = unicodedata.normalize("NFD", filename)
        else:
            filename = unicodedata.normalize("NFC", filename)

        return filename

    def _remove_media_files(self, filenames):
        """
        Marks all files in list filenames as deleted and removes them from the
        media directory.
        """

        # Mark the files as deleted in our db.
        self.col.media.db.executemany("UPDATE media " +
                                      "SET csum = NULL " +
                                      " WHERE fname = ?",
                                      [(f, ) for f in filenames])

        # Remove the files from our media directory if it is present.
        logging.debug('Removing %d files from media dir.' % len(filenames))
        for filename in filenames:
            try:
                os.remove(os.path.join(self.col.media.dir(), filename))
            except OSError as err:
                logging.error("Error when removing file '%s' from media dir: "
                              "%s" % filename, str(err))

    def downloadFiles(self, files):
        import zipfile

        flist = {}
        cnt = 0
        sz = 0
        f = StringIO()
        z = zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED)

        for fname in files:
            z.write(os.path.join(self.col.media.dir(), fname), str(cnt))
            flist[str(cnt)] = fname
            sz += os.path.getsize(os.path.join(self.col.media.dir(), fname))
            if sz > SYNC_ZIP_SIZE or cnt > SYNC_ZIP_COUNT:
                break
            cnt += 1

        z.writestr("_meta", json.dumps(flist))
        z.close()

        return f.getvalue()

    def mediaChanges(self, lastUsn, skey):
        result = []
        usn = self.col.media.lastUsn()
        fname = csum = None

        if lastUsn < usn or lastUsn == 0:
            for fname,mtime,csum, in self.col.media.db.execute("select fname,mtime,csum from media"):
                result.append([fname, usn, csum])

        return json.dumps({'data':result, 'err':''})

    def mediaSanity(self, local=None):
        if self.col.media.mediaCount() == local:
            result = "OK"
        else:
            result = "FAILED"

        return json.dumps({'data':result, 'err':''})

class SyncUserSession(object):
    def __init__(self, name, path, collection_manager, setup_new_collection=None):
        import time
        self.skey = self._generate_session_key()
        self.name = name
        self.path = path
        self.collection_manager = collection_manager
        self.setup_new_collection = setup_new_collection
        self.version = 0
        self.client_version = ''
        self.created = time.time()

        # make sure the user path exists
        if not os.path.exists(path):
            os.mkdir(path)

        self.collection_handler = None
        self.media_handler = None

    def _generate_session_key(self):
        return checksum(str(random.random()))[:8]

    def get_collection_path(self):
        return os.path.realpath(os.path.join(self.path, 'collection.anki2'))

    def get_thread(self):
        return self.collection_manager.get_collection(self.get_collection_path(), self.setup_new_collection)

    def get_handler_for_operation(self, operation, col):
        if operation in SyncCollectionHandler.operations:
            cache_name, handler_class = 'collection_handler', SyncCollectionHandler
        else:
            cache_name, handler_class = 'media_handler', SyncMediaHandler

        if getattr(self, cache_name) is None:
            setattr(self, cache_name, handler_class(col))
        handler = getattr(self, cache_name)
        # The col object may actually be new now! This happens when we close a collection
        # for inactivity and then later re-open it (creating a new Collection object).
        handler.col = col
        return handler

class SimpleSessionManager(object):
    """A simple session manager that keeps the sessions in memory."""

    def __init__(self):
        self.sessions = {}

    def load(self, hkey, session_factory=None):
        return self.sessions.get(hkey)

    def load_from_skey(self, skey, session_factory=None):
        for i in self.sessions:
            if self.sessions[i].skey == skey:
                return self.sessions[i]

    def save(self, hkey, session):
        self.sessions[hkey] = session

    def delete(self, hkey):
        del self.sessions[hkey]

class SimpleUserManager(object):
    """A simple user manager that always allows any user."""

    def authenticate(self, username, password):
        """
        Returns True if this username is allowed to connect with this password. False otherwise.
        Override this to change how users are authenticated.
        """

        return True

    def username2dirname(self, username):
        """
        Returns the directory name for the given user. By default, this is just the username.
        Override this to adjust the mapping between users and their directory.
        """

        return username

class SyncApp(object):
    valid_urls = SyncCollectionHandler.operations + SyncMediaHandler.operations + ['hostKey', 'upload', 'download', 'getDecks']

    def __init__(self, **kw):
        from AnkiServer.threading import getCollectionManager

        self.data_root = os.path.abspath(kw.get('data_root', '.'))
        self.base_url  = kw.get('base_url', '/')
        self.base_media_url  = kw.get('base_media_url', '/')
        self.setup_new_collection = kw.get('setup_new_collection')
        self.hook_pre_sync = kw.get('hook_pre_sync')
        self.hook_post_sync = kw.get('hook_post_sync')
        self.hook_download = kw.get('hook_download')
        self.hook_upload = kw.get('hook_upload')

        try:
            self.session_manager = kw['session_manager']
        except KeyError:
            self.session_manager = SimpleSessionManager()

        try:
            self.user_manager = kw['user_manager']
        except KeyError:
            self.user_manager = SimpleUserManager()

        try:
            self.collection_manager = kw['collection_manager']
        except KeyError:
            self.collection_manager = getCollectionManager()

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
        val = ':'.join([username, str(int(time.time())), ''.join(random.choice(chars) for x in range(8))])
        return hashlib.md5(val).hexdigest()

    def create_session(self, username, user_path):
        return SyncUserSession(username,
                               user_path,
                               self.collection_manager,
                               self.setup_new_collection)

    def _create_session_for_user(self, username):
        """
        Creates a session object for the user and creates a hkey by which we
        can retrieve it on later requests by that user during the same sync
        session.
        Returns the hkey.
        """

        dirname = self.user_manager.username2dirname(username)
        if dirname is None:
            raise HTTPForbidden()

        hkey = self.generateHostKey(username)
        logging.debug("generated session key '%s' for user '%s'"
                      % (hkey, username))

        user_path = os.path.join(self.data_root, dirname)

        session = self.create_session(username, user_path)

        self.session_manager.save(hkey, session)

        return hkey

    def _decode_data(self, data, compression=0):
        import gzip

        if compression:
            buf = gzip.GzipFile(mode="rb", fileobj=StringIO(data))
            data = buf.read()
            buf.close()

        # really lame check for JSON
        if data[0] == '{' and data[-1] == '}':
            data = json.loads(data)
        else:
            data = {'data': data}

        return data

    def operation_upload(self, col, data, session):
        # Verify integrity of the received database file before replacing our
        # existing db.
        temp_db_path = session.get_collection_path() + ".tmp"
        with open(temp_db_path, 'wb') as f:
            f.write(data)

        try:
            test_db = DB(temp_db_path)
            if test_db.scalar("pragma integrity_check") != "ok":
                raise HTTPBadRequest("Integrity check failed for uploaded "
                                     "collection database file.")
            test_db.close()
        except sqlite.Error as e:
            raise HTTPBadRequest("Uploaded collection database file is "
                                 "corrupt.")

        # Overwrite existing db.
        col.close()
        try:
            os.rename(temp_db_path, session.get_collection_path())
        finally:
            col.reopen()

        # If everything went fine, run hook_upload if one is defined.
        if self.hook_upload is not None:
            self.hook_upload(col, session)

        return True

    def operation_download(self, col, session):
        # run hook_download if one is defined
        if self.hook_download is not None:
            self.hook_download(col, session)

        col.close()
        try:
            data = open(session.get_collection_path(), 'rb').read()
        finally:
            col.reopen()
        return data

    @wsgify
    def __call__(self, req):
        # Get and verify the session
        try:
            hkey = req.POST['k']
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
        except ValueError:
            # Bad JSON
            raise HTTPBadRequest()

        if req.path.startswith(self.base_url):
            url = req.path[len(self.base_url):]
            if url not in self.valid_urls:
                raise HTTPNotFound()

            if url == 'getDecks':
                # This is an Anki 1.x client! Tell them to upgrade.
                import zlib, logging
                u = req.params.getone('u')
                if u:
                    logging.warn("'%s' is attempting to sync with an Anki 1.x client" % u)
                return Response(
                    status='200 OK',
                    content_type='application/json',
                    content_encoding='deflate',
                    body=zlib.compress(json.dumps({'status': 'oldVersion'})))

            if url == 'hostKey':
                try:
                    u = data['u']
                    p = data['p']
                except KeyError:
                    raise HTTPForbidden('Must pass username and password')
                if self.user_manager.authenticate(u, p):
                    hkey = self._create_session_for_user(u)

                    result = {'key': hkey}
                    return Response(
                        status='200 OK',
                        content_type='application/json',
                        body=json.dumps(result))
                else:
                    # TODO: do I have to pass 'null' for the client to receive None?
                    raise HTTPForbidden('null')

            if session is None:
                raise HTTPForbidden()

            if url in SyncCollectionHandler.operations + SyncMediaHandler.operations:
                # 'meta' passes the SYNC_VER but it isn't used in the handler
                if url == 'meta':
                    if session.skey == None and req.POST.has_key('s'):
                        session.skey = req.POST['s']
                    if data.has_key('v'):
                        session.version = data['v']
                        del data['v']
                    if data.has_key('cv'):
                        session.client_version = data['cv']
                    self.session_manager.save(hkey, session)
                    session = self.session_manager.load(hkey, self.create_session)

                thread = session.get_thread()

                # run hook_pre_sync if one is defined
                if url == 'start':
                    if self.hook_pre_sync is not None:
                        thread.execute(self.hook_pre_sync, [session])

                result = self._execute_handler_method_in_thread(url, data, session)

                # If it's a complex data type, we convert it to JSON
                if type(result) not in (str, unicode):
                    result = json.dumps(result)

                if url == 'finish':
                    # TODO: Apparently 'finish' isn't when we're done because 'mediaList' comes
                    #       after it... When can we possibly delete the session?
                    #self.session_manager.delete(hkey)

                    # run hook_post_sync if one is defined
                    if self.hook_post_sync is not None:
                        thread.execute(self.hook_post_sync, [session])

                return Response(
                    status='200 OK',
                    content_type='application/json',
                    body=result)

            elif url == 'upload':
                thread = session.get_thread()
                result = thread.execute(self.operation_upload, [data['data'], session])
                return Response(
                    status='200 OK',
                    content_type='text/plain',
                    body='OK' if result else 'Error')

            elif url == 'download':
                thread = session.get_thread()
                result = thread.execute(self.operation_download, [session])
                return Response(
                    status='200 OK',
                    content_type='text/plain',
                    body=result)

            # This was one of our operations but it didn't get handled... Oops!
            raise HTTPInternalServerError()

        # media sync
        elif req.path.startswith(self.base_media_url):
            if session is None:
                raise HTTPForbidden()

            url = req.path[len(self.base_media_url):]

            if url not in self.valid_urls:
                raise HTTPNotFound()

            if url == 'begin' or url == 'mediaChanges' or url == 'uploadChanges':
                data['skey'] = session.skey

            return self._execute_handler_method_in_thread(url, data, session)

        return Response(status='200 OK', content_type='text/plain', body='Anki Sync Server')

    @staticmethod
    def _execute_handler_method_in_thread(method_name, keyword_args, session):
        """
        Gets and runs the handler method specified by method_name inside the
        thread for session. The handler method will access the collection as
        self.col.
        """

        def run_func(col):
            # Retrieve the correct handler method.
            handler = session.get_handler_for_operation(method_name, col)
            handler_method = getattr(handler, method_name)

            res = handler_method(**keyword_args)

            col.save()
            return res

        run_func.func_name = method_name  # More useful debugging messages.

        # Send the closure to the thread for execution.
        thread = session.get_thread()
        result = thread.execute(run_func)

        return result


class SqliteSessionManager(SimpleSessionManager):
    """Stores sessions in a SQLite database to prevent the user from being logged out
    everytime the SyncApp is restarted."""

    def __init__(self, session_db_path):
        SimpleSessionManager.__init__(self)

        self.session_db_path = os.path.abspath(session_db_path)

    def _conn(self):
        new = not os.path.exists(self.session_db_path)
        conn = sqlite.connect(self.session_db_path)
        if new:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE session (hkey VARCHAR PRIMARY KEY, skey VARCHAR, user VARCHAR, path VARCHAR)")
        return conn

    def load(self, hkey, session_factory=None):
        session = SimpleSessionManager.load(self, hkey)
        if session is not None:
            return session

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("SELECT skey, user, path FROM session WHERE hkey=?", (hkey,))
        res = cursor.fetchone()

        if res is not None:
            session = self.sessions[hkey] = session_factory(res[1], res[2])
            session.skey = res[0]
            return session

    def load_from_skey(self, skey, session_factory=None):
        session = SimpleSessionManager.load_from_skey(self, skey)
        if session is not None:
            return session

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("SELECT hkey, user, path FROM session WHERE skey=?", (skey,))
        res = cursor.fetchone()

        if res is not None:
            session = self.sessions[res[0]] = session_factory(res[1], res[2])
            session.skey = skey
            return session

    def save(self, hkey, session):
        SimpleSessionManager.save(self, hkey, session)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("INSERT OR REPLACE INTO session (hkey, skey, user, path) VALUES (?, ?, ?, ?)",
            (hkey, session.skey, session.name, session.path))
        conn.commit()

    def delete(self, hkey):
        SimpleSessionManager.delete(self, hkey)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM session WHERE hkey=?", (hkey,))
        conn.commit()

class SqliteUserManager(SimpleUserManager):
    """Authenticates users against a SQLite database."""

    def __init__(self, auth_db_path):
        self.auth_db_path = os.path.abspath(auth_db_path)

    def authenticate(self, username, password):
        """Returns True if this username is allowed to connect with this password. False otherwise."""

        conn = sqlite.connect(self.auth_db_path)
        cursor = conn.cursor()
        param = (username,)

        cursor.execute("SELECT hash FROM auth WHERE user=?", param)

        db_ret = cursor.fetchone()

        if db_ret != None:
            db_hash = str(db_ret[0])
            salt = db_hash[-16:]
            hashobj = hashlib.sha256()

            hashobj.update(username+password+salt)

        conn.close()

        return (db_ret != None and hashobj.hexdigest()+salt == db_hash)

# Our entry point
def make_app(global_conf, **local_conf):
    if local_conf.has_key('session_db_path'):
        local_conf['session_manager'] = SqliteSessionManager(local_conf['session_db_path'])
    if local_conf.has_key('auth_db_path'):
        local_conf['user_manager'] = SqliteUserManager(local_conf['auth_db_path'])
    return SyncApp(**local_conf)

def main():
    from wsgiref.simple_server import make_server
    from AnkiServer.threading import shutdown

    ankiserver = SyncApp()
    httpd = make_server('', 8001, ankiserver)
    try:
        print "Starting..."
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Exiting ..."
    finally:
        shutdown()

if __name__ == '__main__': main()
