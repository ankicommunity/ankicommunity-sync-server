
from webob.dec import wsgify
from webob.exc import *
from webob import Response

import sqlite3
import hashlib

import AnkiServer

import anki
from anki.sync import LocalServer, MediaSyncer

try:
    import simplejson as json
except ImportError:
    import json

import os

class SyncCollectionHandler(LocalServer):
    operations = ['meta', 'applyChanges', 'start', 'chunk', 'applyChunk', 'sanityCheck2', 'finish']

    def __init__(self, col):
        LocalServer.__init__(self, col)


    def applyChanges(self, changes):
        #self.lmod, lscm, self.maxUsn, lts, dummy = self.meta()
        # TODO: how should we set this value?
        #self.lnewer = 1

        result = LocalServer.applyChanges(self, changes)

        #self.prepareToChunk()

        return result

    #def chunk(self, ):
    #    self.prepareToChunk()
    #    return LocalServer.chunk()

class SyncMediaHandler(MediaSyncer):
    operations = ['remove', 'files', 'addFiles', 'mediaSanity']

    def __init__(self, col):
        MediaSyncer.__init__(self, col)

    def files(self, minUsn=0):
        import zipfile, StringIO

        zipdata, fnames = MediaSyncer.files(self)

        # add a _usn element to the zipdata
        fd = StringIO.StringIO(zipdata)
        zfd = zipfile.ZipFile(fd, "a", compression=zipfile.ZIP_DEFLATED)
        zfd.writestr("_usn", str(minUsn + len(fnames)))
        zfd.close()

        return fd.getvalue()

class SyncUserSession(object):
    def __init__(self, name, path, collection_manager):
        import time
        self.name = name
        self.path = path
        self.collection_manager = collection_manager
        self.version = 0
        self.created = time.time()

        # make sure the user path exists
        if not os.path.exists(path):
            os.mkdir(path)

        self.collection_handler = None
        self.media_handler = None

    def get_collection_path(self):
        return os.path.realpath(os.path.join(self.path, 'collection.anki2'))

    def get_thread(self):
        return self.collection_manager.get_collection(self.get_collection_path())

    def get_handler_for_operation(self, operation, col):
        if operation in SyncCollectionHandler.operations:
            cache_name, handler_class = 'collection_handler', SyncCollectionHandler
        else:
            cache_name, handler_class = 'media_handler', SyncMediaHandler

        if getattr(self, cache_name) is None:
            setattr(self, cache_name, handler_class(col))
        return getattr(self, cache_name)

class SyncApp(object):
    valid_urls = SyncCollectionHandler.operations + SyncMediaHandler.operations + ['hostKey', 'upload', 'download', 'getDecks']

    def __init__(self, **kw):
        from AnkiServer.threading import getCollectionManager

        self.data_root = os.path.abspath(kw.get('data_root', '.'))
        self.base_url  = kw.get('base_url', '/')
        self.auth_db_path = os.path.abspath(kw.get('auth_db_path', '.'))
        self.sessions = {}

        try:
            self.collection_manager = kw['collection_manager']
        except KeyError:
            self.collection_manager = getCollectionManager()

        # make sure the base_url has a trailing slash
        if len(self.base_url) == 0:
            self.base_url = '/'
        elif self.base_url[-1] != '/':
            self.base_url = base_url + '/'

    def authenticate(self, username, password):
        """
        Returns True if this username is allowed to connect with this password. False otherwise.

        Override this to change how users are authenticated.
        """

        return False

    def username2dirname(self, username):
        """
        Returns the directory name for the given user. By default, this is just the username.

        Override this to adjust the mapping between users and their directory.
        """

        return username

    def generateHostKey(self, username):
        """Generates a new host key to be used by the given username to identify their session.
        This values is random."""

        import hashlib, time, random, string
        chars = string.ascii_letters + string.digits
        val = ':'.join([username, str(int(time.time())), ''.join(random.choice(chars) for x in range(8))])
        return hashlib.md5(val).hexdigest()

    def create_session(self, hkey, username, user_path):
        """Creates, stores and returns a new session for the given hkey and username."""

        session = self.sessions[hkey] = SyncUserSession(username, user_path, self.collection_manager)
        return session

    def load_session(self, hkey):
        return self.sessions.get(hkey)

    def save_session(self, hkey, session):
        pass

    def delete_session(self, hkey):
        del self.sessions[hkey]

    def _decode_data(self, data, compression=0):
        import gzip, StringIO

        if compression:
            buf = gzip.GzipFile(mode="rb", fileobj=StringIO.StringIO(data))
            data = buf.read()
            buf.close()

        # really lame check for JSON
        if data[0] == '{' and data[-1] == '}':
            data = json.loads(data)
        else:
            data = {'data': data}

        return data

    def operation_upload(self, col, data, session):
        # TODO: deal with thread pool

        fd = open(session.get_collection_path(), 'wb')
        fd.write(data)
        fd.close()

    def operation_download(self, col, data, session):
        pass

    @wsgify
    def __call__(self, req):
        print req.path
        if req.path.startswith(self.base_url):
            url = req.path[len(self.base_url):]
            if url not in self.valid_urls:
                raise HTTPNotFound()

            if url == 'getDecks':
                # This is an Anki 1.x client! Tell them to upgrade.
                import zlib
                return Response(
                        status='200 OK',
                        content_type='application/json',
                        content_encoding='deflate',
                        body=zlib.compress(json.dumps({'status': 'oldVersion'})))

            try:
                compression = req.POST['c']
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
            print 'data:', data

            if url == 'hostKey':
                try:
                    u = data['u']
                    p = data['p']
                except KeyError:
                    raise HTTPForbidden('Must pass username and password')
                if self.authenticate(u, p):
                    dirname = self.username2dirname(u)
                    if dirname is None:
                        raise HTTPForbidden()

                    hkey = self.generateHostKey(u)
                    user_path = os.path.join(self.data_root, dirname)
                    session = self.create_session(hkey, u, user_path)

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
            session = self.load_session(hkey)
            if session is None:
                raise HTTPForbidden()

            if url in SyncCollectionHandler.operations + SyncMediaHandler.operations:
                # 'meta' passes the SYNC_VER but it isn't used in the handler
                if url == 'meta' and data.has_key('v'):
                    session.version = data['v']
                    del data['v']

                # Create a closure to run this operation inside of the thread allocated to this collection
                def runFunc(col):
                    handler = session.get_handler_for_operation(url, col)
                    func = getattr(handler, url)
                    result = func(**data)
                    handler.col.save()
                    return result
                runFunc.func_name = url

                # Send to the thread to execute
                thread = session.get_thread()
                result = thread.execute(runFunc)

                # If it's a complex data type, we convert it to JSON
                if type(result) not in (str, unicode):
                    result = json.dumps(result)

                if url == 'finish':
                    self.delete_session(hkey)

                return Response(
                    status='200 OK',
                    content_type='application/json',
                    body=result)

            elif url in ('upload', 'download'):
                if url == 'upload':
                    func = self.operation_upload
                else:
                    func = self.operation_download

                thread = session.get_thread()
                thread.execute(self.operation_upload, [data['data'], session])

                return Response(
                    status='200 OK',
                    content_type='text/plain',
                    body='OK')

            # This was one of our operations but it didn't get handled... Oops!
            raise HTTPInternalServerError()

        return Response(status='200 OK', content_type='text/plain', body='Anki Sync Server')

class DatabaseAuthSyncApp(SyncApp):
    def authenticate(self, username, password):
        """Returns True if this username is allowed to connect with this password. False otherwise."""

        conn = sqlite3.connect(self.auth_db_path)
        cursor = conn.cursor()
        param = (username,)

        cursor.execute("SELECT hash FROM auth WHERE user=?", param)

        db_ret = cursor.fetchone()

        if db_ret != None:
            db_hash = str(db_ret[0])
            salt = db_hash[-16:]
            hashobj = hashlib.sha256()

            hashobj.update(username+password+salt)

        return (db_ret != None and hashobj.hexdigest()+salt == db_hash)

# Our entry point
def make_app(global_conf, **local_conf):
    return DatabaseAuthSyncApp(**local_conf)

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

