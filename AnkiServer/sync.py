
from webob.dec import wsgify
from webob.exc import *
from webob import Response

# TODO: I don't think this should have to be at the top of every module!
import sys
sys.path.insert(0, "/usr/share/anki")

#import anki
#from anki.sync import HttpSyncServer, CHUNK_SIZE
#from anki.db import sqlite
#from anki.utils import checksum
import anki
from anki.sync import LocalServer, MediaSyncer
# TODO: shouldn't use this directly! This should be through the thread pool
from anki.storage import Collection

#import AnkiServer.deck

#import MySQLdb

try:
    import simplejson as json
except ImportError:
    import json

import os, zlib, tempfile, time

class SyncCollectionHandler(LocalServer):
    operations = ['meta', 'applyChanges', 'start', 'chunk', 'applyChunk', 'sanityCheck2', 'finish']

    def __init__(self, col):
        LocalServer.__init__(self, col)

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

class SyncUser(object):
    def __init__(self, name, path):
        # make sure the user path exists
        if not os.path.exists(path):
            os.mkdir(path)

        import time
        self.name = name
        self.path = path
        self.version = 0
        self.created = time.time()

    def get_collection_path(self):
        return os.path.realpath(os.path.join(self.path, 'collection.anki2'))

class SyncApp(object):
    valid_urls = SyncCollectionHandler.operations + SyncMediaHandler.operations + ['hostKey', 'upload']

    def __init__(self, **kw):
        self.data_root = os.path.abspath(kw.get('data_root', '.'))
        self.base_url  = kw.get('base_url', '/')
        self.users = {}

        # make sure the base_url has a trailing slash
        if len(self.base_url) == 0:
            self.base_url = '/'
        elif self.base_url[-1] != '/':
            self.base_url = base_url + '/'

    def authenticate(self, username, password):
        """Override this to change how users are authenticated."""
        # TODO: This should have the exact opposite default ;-)
        return True

    def username2dirname(self, username):
        """Override this to adjust the mapping between users and their directory."""
        return username
    
    def generateHostKey(self, username):
        import hashlib, time, random, string
        chars = string.ascii_letters + string.digits
        val = ':'.join([username, str(int(time.time())), ''.join(random.choice(chars) for x in range(8))])
        return hashlib.md5(val).hexdigest()

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

    @wsgify
    def __call__(self, req):
        print req.path
        if req.path.startswith(self.base_url):
            url = req.path[len(self.base_url):]
            if url not in self.valid_urls:
                raise HTTPNotFound()

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

                    # setup user and map to a hkey
                    hkey = self.generateHostKey(u)
                    user_path = os.path.join(self.data_root, dirname)
                    self.users[hkey] = SyncUser(u, user_path)

                    result = {'key': hkey}
                    return Response(
                        status='200 OK',
                        content_type='application/json',
                        body=json.dumps(result))
                else:
                    # TODO: do I have to pass 'null' for the client to receive None?
                    raise HTTPForbidden('null')

            # verify the hostkey
            try:
                hkey = req.POST['k']
                user = self.users[hkey]
            except KeyError:
                raise HTTPForbidden()

            if url in SyncCollectionHandler.operations + SyncMediaHandler.operations:
                # TODO: use thread pool!
                col = Collection(user.get_collection_path())

                if url in SyncCollectionHandler.operations:
                    handler = SyncCollectionHandler(col)
                else:
                    handler = SyncMediaHandler(col)

                func = getattr(handler, url)

                # 'meta' passes the SYNC_VER but it isn't used in the handler
                if url == 'meta' and data.has_key('v'):
                    user.version = data['v']
                    del data['v']

                try:
                    result = func(**data)
                #except Exception, e:
                #    print e
                #    raise HTTPInternalServerError()
                finally:
                    col.close()

                # If it's a complex data type, we convert it to JSON
                if type(result) not in (str, unicode):
                    result = json.dumps(result)
        
                return Response(
                    status='200 OK',
                    content_type='application/json',
                    body=result)

            elif url == 'upload':
                # TODO: deal with thread pool

                fd = open(user.get_collection_path(), 'wb')
                fd.write(data['data'])
                fd.close()

                return Response(
                    status='200 OK',
                    content_type='text/plain',
                    body='OK')

            # TODO: turn this into a 500 error in the future!
            return Response(status='503 Temporarily Unavailable ', content_type='text/plain', body='This operation isn\'t implemented yet.')

        return Response(status='200 OK', content_type='text/plain', body='Anki Sync Server')

# Our entry point
def make_app(global_conf, **local_conf):
    return SyncApp(**local_conf)

def main():

    from wsgiref.simple_server import make_server

    ankiserver = SyncApp()
    httpd = make_server('', 8001, ankiserver)
    try:
        print "Starting..."
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Exiting ..."
    finally:
        #AnkiServer.deck.thread_pool.shutdown()
        pass

if __name__ == '__main__': main()

