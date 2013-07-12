
from webob.dec import wsgify
from webob.exc import *
from webob import Response

import anki
from anki.sync import HttpSyncServer, CHUNK_SIZE
from anki.db import sqlite
from anki.utils import checksum

import AnkiServer.deck

import MySQLdb

try:
    import simplejson as json
except ImportError:
    import json

import os, zlib, tempfile, time

def makeArgs(mdict):
    d = dict(mdict.items())
    # TODO: use password/username/version for something?
    for k in ['p','u','v','d']:
        if d.has_key(k):
            del d[k]
    return d

class FileIterable(object):
    def __init__(self, fn):
        self.fn = fn
    def __iter__(self):
        return FileIterator(self.fn)

class FileIterator(object):
    def __init__(self, fn):
        self.fn = fn
        self.fo = open(self.fn, 'rb')
        self.c = zlib.compressobj()
        self.flushed = False
    def __iter__(self):
        return self
    def next(self):
        data = self.fo.read(CHUNK_SIZE)
        if not data:
            if not self.flushed:
                self.flushed = True
                return self.c.flush()
            else:
                raise StopIteration
        return self.c.compress(data)

def lock_deck(path):
    """ Gets exclusive access to this deck path.  If there is a DeckThread running on this
    deck, this will wait for its current operations to complete before temporarily stopping
    it. """

    from AnkiServer.deck import thread_pool

    if thread_pool.decks.has_key(path):
        thread_pool.decks[path].stop_and_wait()
    thread_pool.lock(path)

def unlock_deck(path):
    """ Release exclusive access to this deck path. """
    from AnkiServer.deck import thread_pool
    thread_pool.unlock(path)

class SyncAppHandler(HttpSyncServer):
    operations = ['summary','applyPayload','finish','createDeck','getOneWayPayload']

    def __init__(self):
        HttpSyncServer.__init__(self)

    def createDeck(self, name):
        # The HttpSyncServer.createDeck doesn't return a valid value!  This seems to be
        # a bug in libanki.sync ...
        return self.stuff({"status": "OK"})

    def finish(self):
        # The HttpSyncServer has no finish() function...  I can only assume this is a bug too!
        return self.stuff("OK")

class SyncApp(object):
    valid_urls = SyncAppHandler.operations + ['getDecks','fullup','fulldown']

    def __init__(self, **kw):
        self.data_root = os.path.abspath(kw.get('data_root', '.'))
        self.base_url  = kw.get('base_url', '/')
        self.users = {}

        # make sure the base_url has a trailing slash
        if len(self.base_url) == 0:
            self.base_url = '/'
        elif self.base_url[-1] != '/':
            self.base_url = base_url + '/'

        # setup mysql connection
        mysql_args = {}
        for k, v in kw.items():
            if k.startswith('mysql.'):
                mysql_args[k[6:]] = v
        self.mysql_args = mysql_args
        self.conn = None

        # get SQL statements
        self.sql_check_password = kw.get('sql_check_password')
        self.sql_username2dirname = kw.get('sql_username2dirname')

    default_libanki_version = '.'.join(anki.version.split('.')[:2])

    def user_libanki_version(self, u):
        try:
            s = self.users[u]['libanki']
        except KeyError:
            return self.default_libanki_version

        parts = s.split('.')
        if parts[0] == '1':
            if parts[1] == '0':
                return '1.0'
            elif parts[1] in ('1','2'):
                return '1.2'

        return self.default_libanki_version

    # Mimcs from anki.sync.SyncTools.stuff()
    def _stuff(self, data):
        return zlib.compress(json.dumps(data))

    def _connect_mysql(self):
        if self.conn is None and len(self.mysql_args) > 0:
            self.conn = MySQLdb.connect(**self.mysql_args)

    def _execute_sql(self, sql, args=()):
        self._connect_mysql()
        try:
            cur = self.conn.cursor()
            cur.execute(sql, args)
        except MySQLdb.OperationalError, e:
            if e.args[0] == 2006:
                # MySQL server has gone away message
                self.conn = None
                self._connect_mysql()
                cur = self.conn.cursor()
                cur.execute(sql, args)
        return cur

    def check_password(self, username, password):
        if len(self.mysql_args) > 0 and self.sql_check_password is not None:
            cur = self._execute_sql(self.sql_check_password, (username, password))
            row = cur.fetchone()
            return row is not None

        return True

    def username2dirname(self, username):
        if len(self.mysql_args) > 0 and self.sql_username2dirname is not None:
            cur = self._execute_sql(self.sql_username2dirname, (username,))
            row = cur.fetchone()
            if row is None:
                return None
            return str(row[0])

        return username

    def _getDecks(self, user_path):
        decks = {}

        if os.path.exists(user_path):
            # It is a dict of {'deckName':[modified,lastSync]}
            for fn in os.listdir(unicode(user_path, 'utf-8')):
                if len(fn) > 5 and fn[-5:] == '.anki':
                    d = os.path.abspath(os.path.join(user_path, fn))

                    # For simplicity, we will always open a thread.  But this probably
                    # isn't necessary!
                    thread = AnkiServer.deck.thread_pool.start(d)
                    def lookupModifiedLastSync(wrapper):
                        deck = wrapper.open()
                        return [deck.modified, deck.lastSync]
                    res = thread.execute(lookupModifiedLastSync, [thread.wrapper])

#                    if thread_pool.threads.has_key(d):
#                        thread = thread_pool.threads[d]
#                        def lookupModifiedLastSync(wrapper):
#                            deck = wrapper.open()
#                            return [deck.modified, deck.lastSync]
#                        res = thread.execute(lookup, [thread.wrapper])
#                    else:
#                        conn = sqlite.connect(d)
#                        cur = conn.cursor()
#                        cur.execute("select modified, lastSync from decks")
#
#                        res = list(cur.fetchone())
#
#                        cur.close()
#                        conn.close()

                    #self.decks[fn[:-5]] = ["%.5f" % x for x in res]
                    decks[fn[:-5]] = res

        # same as HttpSyncServer.getDecks()
        return self._stuff({
            "status": "OK",
            "decks": decks,
            "timestamp": time.time(),
            })

    def _fullup(self, wrapper, infile, version):
        wrapper.close()
        path = wrapper.path

        # DRS: most of this function was graciously copied
        # from anki.sync.SyncTools.fullSyncFromServer()
        (fd, tmpname) = tempfile.mkstemp(dir=os.getcwd(), prefix="fullsync")
        outfile = open(tmpname, 'wb')
        decomp = zlib.decompressobj()
        while 1:
            data = infile.read(CHUNK_SIZE)
            if not data:
                outfile.write(decomp.flush())
                break
            outfile.write(decomp.decompress(data))
        infile.close()
        outfile.close()
        os.close(fd)
        # if we were successful, overwrite old deck
        if os.path.exists(path):
            os.unlink(path)
        os.rename(tmpname, path)
        # reset the deck name
        c = sqlite.connect(path)
        lastSync = time.time()
        if version == '1':
            c.execute("update decks set lastSync = ?", [lastSync])
        elif version == '2':
            c.execute("update decks set syncName = ?, lastSync = ?",
                      [checksum(path.encode("utf-8")), lastSync])
        c.commit()
        c.close()

        return lastSync

    def _stuffedResp(self, data):
        return Response(
            status='200 OK',
            content_type='application/json',
            content_encoding='deflate',
            body=data)

    @wsgify
    def __call__(self, req):
        if req.path.startswith(self.base_url):
            url = req.path[len(self.base_url):]
            if url not in self.valid_urls:
                raise HTTPNotFound()
            
            # get and check username and password
            try:
                u = req.str_params.getone('u')
                p = req.str_params.getone('p')
            except KeyError:
                raise HTTPBadRequest('Must pass username and password')
            if not self.check_password(u, p):
                #raise HTTPBadRequest('Incorrect username or password')
                return self._stuffedResp(self._stuff({'status':'invalidUserPass'}))
            dirname = self.username2dirname(u)
            if dirname is None:
                raise HTTPBadRequest('Incorrect username or password')
            user_path = os.path.join(self.data_root, dirname)

            # get and lock the (optional) deck for this request
            d = None
            try:
                d = unicode(req.str_params.getone('d'), 'utf-8')
                # AnkiDesktop actually passes us the string value 'None'!
                if d == 'None':
                    d = None
            except KeyError:
                pass
            if d is not None:
                # get the full deck path name
                d = os.path.abspath(os.path.join(user_path, d)+'.anki')
                if d[:len(user_path)] != user_path:
                    raise HTTPBadRequest('Bad deck name')
                thread = AnkiServer.deck.thread_pool.start(d)
            else:
                thread = None

            if url == 'getDecks':
                # force the version up to 1.2.x
                v = req.str_params.getone('libanki')
                if v.startswith('0.') or v.startswith('1.0'):
                    return self._stuffedResp(self._stuff({'status':'oldVersion'}))

                # store the data the user passes us keyed with the username.  This
                # will be used later by SyncAppHandler for version compatibility.
                self.users[u] = makeArgs(req.str_params)
                return self._stuffedResp(self._getDecks(user_path))

            elif url in SyncAppHandler.operations:
                handler = SyncAppHandler()
                func = getattr(handler, url)
                args = makeArgs(req.str_params)

                if thread is not None:
                    # If this is for a specific deck, then it needs to run
                    # inside of the DeckThread.
                    def runFunc(wrapper):
                        handler.deck = wrapper.open()
                        ret = func(**args)
                        handler.deck.save()
                        return ret
                    runFunc.func_name = url
                    ret = thread.execute(runFunc, [thread.wrapper])
                else:
                    # Otherwise, we can simply execute it in this thread.
                    ret = func(**args)

                # clean-up user data stored in getDecks
                if url == 'finish':
                    del self.users[u]

                return self._stuffedResp(ret)

            elif url == 'fulldown':
                # set the syncTime before we send it
                def setupForSync(wrapper):
                    wrapper.close()
                    c = sqlite.connect(d)
                    lastSync = time.time()
                    c.execute("update decks set lastSync = ?", [lastSync])
                    c.commit()
                    c.close()
                thread.execute(setupForSync, [thread.wrapper])

                return Response(status='200 OK', content_type='application/octet-stream', content_encoding='deflate', content_disposition='attachment; filename="'+os.path.basename(d).encode('utf-8')+'"', app_iter=FileIterable(d))
            elif url == 'fullup':
                #version = self.user_libanki_version(u)
                try:
                    version = req.str_params.getone('v')
                except KeyError:
                    version = '1'

                infile = req.str_params['deck'].file
                lastSync = thread.execute(self._fullup, [thread.wrapper, infile, version])

                # append the 'lastSync' value for libanki 1.1 and 1.2
                if version == '2':
                    body = 'OK '+str(lastSync)
                else:
                    body = 'OK'

                return Response(status='200 OK', content_type='application/text', body=body)

        return Response(status='200 OK', content_type='text/plain', body='Anki Server')

# Our entry point
def make_app(global_conf, **local_conf):
    return SyncApp(**local_conf)

def main():
    from wsgiref.simple_server import make_server

    ankiserver = DeckApp('.', '/sync/')
    httpd = make_server('', 8001, ankiserver)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Exiting ..."
    finally:
        AnkiServer.deck.thread_pool.shutdown()

if __name__ == '__main__': main()

