
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

import AnkiServer

import anki
from anki.sync import Syncer, MediaSyncer
from anki.utils import intTime, checksum
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

        version_int = [int(x) for x in version.split('.')]

        # Some insanity added in Anki 2.0.13
        if client == 'ankidesktop' and version_int[0] >= 2 and version_int[1] >= 0 and version_int[2] >= 13:
            return {
              'scm': self.col.scm,
              'ts': intTime(),
              'mod': self.col.mod,
              'usn': self.col._usn,
              'musn': self.col.media.usn(),
              'msg': '',
              'cont': True,
            }
        else:
            return (self.col.mod, self.col.scm, self.col._usn, intTime(), self.col.media.usn())

class SyncMediaHandler(MediaSyncer):
    operations = ['remove', 'files', 'addFiles', 'mediaSanity', 'mediaList']

    def __init__(self, col):
        MediaSyncer.__init__(self, col)

    def remove(self, fnames, minUsn):
        rrem = MediaSyncer.remove(self, fnames, minUsn)
        # increment the USN for each file removed
        #self.col.media.setUsn(self.col.media.usn() + len(rrem))
        return rrem

    def files(self, minUsn=0, need=None):
        """Gets files from the media database and returns them as ZIP file data."""

        import zipfile

        # The client can pass None - I'm not sure what the correct action is in that case,
        # for now, we're going to resync everything.
        if need is None:
            need = self.mediaList()

        # Comparing minUsn to need, we attempt to determine which files have already
        # been sent, and we remove them from the front of the list.
        need = need[len(need) - (self.col.media.usn() - minUsn):]

        # Copied and modified from anki.media.MediaManager.zipAdded(). Instead of going
        # over the log, we loop over the files needed and increment the USN along the
        # way. The zip also has an additional '_usn' member, which the client uses to
        # update the usn on their end.

        f = StringIO()
        z = zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED)
        sz = 0
        cnt = 0
        files = {}
        while 1:
            if len(need) == 0:
                # add a flag so the server knows it can clean up
                z.writestr("_finished", "")
                break
            fname = need.pop()
            minUsn += 1
            z.write(os.path.join(self.col.media.dir(), fname), str(cnt))
            files[str(cnt)] = fname
            sz += os.path.getsize(os.path.join(self.col.media.dir(), fname))
            if sz > SYNC_ZIP_SIZE or cnt > SYNC_ZIP_COUNT:
                break
            cnt += 1
        z.writestr("_meta", json.dumps(files))
        z.writestr("_usn", str(minUsn))
        z.close()

        return f.getvalue()

    def addFiles(self, data):
        """Adds files based from ZIP file data and returns the usn."""

        import zipfile

        # The argument name is 'zip' on MediaSyncer, but we always use 'data' when
        # we receive non-JSON data. We have to override to receive the right argument!
        #MediaSyncer.addFiles(self, zip=fd.getvalue())

        usn = self.col.media.usn()

        # Copied from anki.media.MediaManager.syncAdd(). Modified to not need the
        # _usn file and, instead, to increment the server usn with each file added.

        f = StringIO(data)
        z = zipfile.ZipFile(f, "r")
        finished = False
        meta = None
        media = []
        sizecnt = 0
        # get meta info first
        assert z.getinfo("_meta").file_size < 100000
        meta = json.loads(z.read("_meta"))
        # then loop through all files
        for i in z.infolist():
            # check for zip bombs
            sizecnt += i.file_size
            assert sizecnt < 100*1024*1024
            if i.filename == "_meta" or i.filename == "_usn":
                # ignore previously-retrieved meta
                continue
            elif i.filename == "_finished":
                # last zip in set
                finished = True
            else:
                data = z.read(i)
                csum = checksum(data)
                name = meta[i.filename]
                # can we store the file on this system?
                # NOTE: this function changed it's name in Anki 2.0.12 to media.hasIllegal()
                if hasattr(self.col.media, 'illegal') and self.col.media.illegal(name):
                    continue
                if hasattr(self.col.media, 'hasIllegal') and self.col.media.hasIllegal(name):
                    continue
                # save file
                open(os.path.join(self.col.media.dir(), name), "wb").write(data)
                # update db
                media.append((name, csum, self.col.media._mtime(os.path.join(self.col.media.dir(), name))))
                # remove entries from local log
                self.col.media.db.execute("delete from log where fname = ?", name)
                usn += 1
        # update media db and note new starting usn
        if media:
            self.col.media.db.executemany(
                "insert or replace into media values (?,?,?)", media)
        self.col.media.setUsn(usn) # commits
        # if we have finished adding, we need to record the new folder mtime
        # so that we don't trigger a needless scan
        if finished:
            self.col.media.syncMod()

        return usn

    def mediaSanity(self, client=None):
        # TODO: Do something with 'client' argument?
        return self.col.media.sanityCheck()

    def mediaList(self):
        """Returns a list of all the fnames in this collections media database."""
        fnames = []
        for fname, in self.col.media.db.execute("select fname from media"):
            fnames.append(fname)
        fnames.sort()
        return fnames

class SyncUserSession(object):
    def __init__(self, name, path, collection_manager, setup_new_collection=None):
        import time
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

    def generateHostKey(self, username):
        """Generates a new host key to be used by the given username to identify their session.
        This values is random."""

        import hashlib, time, random, string
        chars = string.ascii_letters + string.digits
        val = ':'.join([username, str(int(time.time())), ''.join(random.choice(chars) for x in range(8))])
        return hashlib.md5(val).hexdigest()

    def create_session(self, username, user_path):
        return SyncUserSession(username, user_path, self.collection_manager, self.setup_new_collection)

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
        col.close()

        # TODO: we should verify the database integrity before perminantly overwriting
        # (ie. use a temporary file) and declaring this a success!
        #
        # d = DB(path)
        # assert d.scalar("pragma integrity_check") == "ok"
        # d.close()
        #
        try:
            with open(session.get_collection_path(), 'wb') as fd:
                fd.write(data)
        finally:
            col.reopen()

        # run hook_upload if one is defined
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
        #print req.path
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
            #print 'data:', data

            if url == 'hostKey':
                try:
                    u = data['u']
                    p = data['p']
                except KeyError:
                    raise HTTPForbidden('Must pass username and password')
                if self.user_manager.authenticate(u, p):
                    dirname = self.user_manager.username2dirname(u)
                    if dirname is None:
                        raise HTTPForbidden()

                    hkey = self.generateHostKey(u)
                    user_path = os.path.join(self.data_root, dirname)
                    session = self.create_session(u, user_path)
                    self.session_manager.save(hkey, session)

                    result = {'key': hkey}
                    return Response(
                        status='200 OK',
                        content_type='application/json',
                        body=json.dumps(result))
                else:
                    # TODO: do I have to pass 'null' for the client to receive None?
                    raise HTTPForbidden('null')

            # Get and verify the session
            try:
                hkey = req.POST['k']
            except KeyError:
                raise HTTPForbidden()
            session = self.session_manager.load(hkey, self.create_session)
            if session is None:
                raise HTTPForbidden()

            if url in SyncCollectionHandler.operations + SyncMediaHandler.operations:
                # 'meta' passes the SYNC_VER but it isn't used in the handler
                if url == 'meta':
                    if data.has_key('v'):
                        session.version = data['v']
                        del data['v']
                    if data.has_key('cv'):
                        session.client_version = data['cv']

                thread = session.get_thread()

                # run hook_pre_sync if one is defined
                if url == 'start':
                    if self.hook_pre_sync is not None:
                        thread.execute(self.hook_pre_sync, [session])

                # Create a closure to run this operation inside of the thread allocated to this collection
                def runFunc(col):
                    handler = session.get_handler_for_operation(url, col)
                    func = getattr(handler, url)
                    result = func(**data)
                    col.save()
                    return result
                runFunc.func_name = url

                # Send to the thread to execute
                result = thread.execute(runFunc)

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

        return Response(status='200 OK', content_type='text/plain', body='Anki Sync Server')

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
            cursor.execute("CREATE TABLE session (hkey VARCHAR PRIMARY KEY, user VARCHAR, path VARCHAR)")
        return conn

    def load(self, hkey, session_factory=None):
        session = SimpleSessionManager.load(self, hkey)
        if session is not None:
            return session

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("SELECT user, path FROM session WHERE hkey=?", (hkey,))
        res = cursor.fetchone()

        if res is not None:
            session = self.sessions[hkey] = session_factory(res[0], res[1])
            return session

    def save(self, hkey, session):
        SimpleSessionManager.save(self, hkey, session)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("INSERT OR REPLACE INTO session (hkey, user, path) VALUES (?, ?, ?)",
            (hkey, session.name, session.path))
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
