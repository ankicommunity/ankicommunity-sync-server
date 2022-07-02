# -*- coding: utf-8 -*-
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

# Taken from https://github.com/ankitects/anki/blob/cca3fcb2418880d0430a5c5c2e6b81ba260065b7/anki/sync.py

import io
import gzip
import random
import requests
import json
import os
from typing import List,Tuple

from anki.db import DB, DBError
from anki.utils import ids2str, intTime, platDesc, checksum, devMode
from anki.consts import *
from anki.config import ConfigManager
from anki.utils import versionWithBuild
import anki
from anki.lang import ngettext


# https://github.com/ankitects/anki/blob/04b1ca75599f18eb783a8bf0bdeeeb32362f4da0/rslib/src/sync/http_client.rs#L11
SYNC_VER = 10
# https://github.com/ankitects/anki/blob/cca3fcb2418880d0430a5c5c2e6b81ba260065b7/anki/consts.py#L50
SYNC_ZIP_SIZE = int(2.5*1024*1024)
# https://github.com/ankitects/anki/blob/cca3fcb2418880d0430a5c5c2e6b81ba260065b7/anki/consts.py#L51
SYNC_ZIP_COUNT = 25

# syncing vars
HTTP_TIMEOUT = 90
HTTP_PROXY = None
HTTP_BUF_SIZE = 64*1024

# Incremental syncing
##########################################################################

class Syncer(object):
    def __init__(self, col, server=None):
        self.col = col
        self.server = server

# new added functions related to Syncer:
#  these are removed from latest anki module
########################################################################
    def scm(self):
        """return schema"""
        scm=self.col.db.scalar("select scm from col")
        return scm
    def increment_usn(self):
        """usn+1 in db"""
        self.col.db.execute("update col set usn = usn + 1")
    def set_modified_time(self,now:int):
        self.col.db.execute("update col set mod=?", now)
    def set_last_sync(self,now:int):
        self.col.db.execute("update col set ls = ?", now)
#########################################################################
    def meta(self):
        return dict(
            mod=self.col.mod,
            scm=self.col.scm,
            usn=self.col._usn,
            ts=intTime(),
            musn=0,
            msg="",
            cont=True
        )

    def changes(self):
        "Bundle up small objects."
        d = dict(models=self.getModels(),
                 decks=self.getDecks(),
                 tags=self.getTags())
        if self.lnewer:
            d['conf'] = self.col.all_config()
            d['crt'] = self.col.crt
        return d

    def mergeChanges(self, lchg, rchg):
        # then the other objects
        self.mergeModels(rchg['models'])
        self.mergeDecks(rchg['decks'])
        if 'conf' in rchg:
            self.mergeConf(rchg['conf'])
        # this was left out of earlier betas
        if 'crt' in rchg:
            self.col.crt = rchg['crt']
        self.prepareToChunk()
#     this fn was cloned from anki module(version 2.1.36)
    def basicCheck(self) -> bool:
        "Basic integrity check for syncing. True if ok."
        # cards without notes
        if self.col.db.scalar(
            """
select 1 from cards where nid not in (select id from notes) limit 1"""
        ):
            return False
        # notes without cards or models
        if self.col.db.scalar(
            """
select 1 from notes where id not in (select distinct nid from cards)
or mid not in %s limit 1"""
            % ids2str(self.col.models.ids())
        ):
            return False
        # invalid ords
        for m in self.col.models.all():
            # ignore clozes
            if m["type"] != MODEL_STD:
                continue
            if self.col.db.scalar(
                """
select 1 from cards where ord not in %s and nid in (
select id from notes where mid = ?) limit 1"""
                % ids2str([t["ord"] for t in m["tmpls"]]),
                m["id"],
            ):
                return False
        return True
    
    def sanityCheck(self):
        tables=["cards", 
            "notes",
            "revlog",
            "graves",
            "decks",
            "deck_config",
            "tags",
            "notetypes",
        ]
        for tb in tables:
            if  self.col.db.scalar(f'select null from {tb} where usn=-1'):
                return f'table had usn=-1: {tb}'
        self.col.sched.reset()
        
        # return summary of deck
        # make sched.counts() equal to default [0,0,0]
        # to make sure sync normally if sched.counts()
        # are not equal between different clients due to
        # different deck selection 
        return [
            list([0,0,0]),
            self.col.db.scalar("select count() from cards"),
            self.col.db.scalar("select count() from notes"),
            self.col.db.scalar("select count() from revlog"),
            self.col.db.scalar("select count() from graves"),
            len(self.col.models.all()),
            len(self.col.decks.all()),
            len(self.col.decks.all_config()),
        ]

    def usnLim(self):
        return "usn = -1"

    def finish(self, now=None):
        if now is not None:
        # ensure we save the mod time even if no changes made
            self.set_modified_time(now)
            self.set_last_sync(now)
            self.increment_usn()
            self.col.save()
            return now
        # even though that now is None will not happen,have to match a gurad case
        return None

    # Chunked syncing
    ##########################################################################

    def prepareToChunk(self):
        self.tablesLeft = ["revlog", "cards", "notes"]
        self.cursor = None

    def queryTable(self, table):
        lim = self.usnLim()
        if table == "revlog":
            return self.col.db.execute("""
select id, cid, ?, ease, ivl, lastIvl, factor, time, type
from revlog where %s""" % lim, self.maxUsn)
        elif table == "cards":
            return self.col.db.execute("""
select id, nid, did, ord, mod, ?, type, queue, due, ivl, factor, reps,
lapses, left, odue, odid, flags, data from cards where %s""" % lim, self.maxUsn)
        else:
            return self.col.db.execute("""
select id, guid, mid, mod, ?, tags, flds, '', '', flags, data
from notes where %s""" % lim, self.maxUsn)

    def chunk(self):
        buf = dict(done=False)
        while self.tablesLeft:
            curTable = self.tablesLeft.pop()
            buf[curTable] = self.queryTable(curTable)
            self.col.db.execute(
                f"update {curTable} set usn=? where usn=-1", self.maxUsn
            )
        if not self.tablesLeft:
            buf['done'] = True
        return buf

    def applyChunk(self, chunk):
        if "revlog" in chunk:
            self.mergeRevlog(chunk['revlog'])
        if "cards" in chunk:
            self.mergeCards(chunk['cards'])
        if "notes" in chunk:
            self.mergeNotes(chunk['notes'])

    # Deletions
    ##########################################################################

    def add_grave(self, ids: List[int], type: int,usn: int):
        items=[(id,type,usn) for id in ids]
        # make sure table graves fields order and schema version match
        # query sql1='pragma table_info(graves)' version query schema='select ver from col'
        self.col.db.executemany(
            "INSERT OR IGNORE INTO graves (oid, type, usn) VALUES (?, ?, ?)" ,
            items)
    
    def apply_graves(self, graves,latest_usn: int):
         # remove card and the card's orphaned notes
        self.col.remove_cards_and_orphaned_notes(graves['cards'])
        self.add_grave(graves['cards'], REM_CARD,latest_usn)
        # only notes
        self.col.remove_notes(graves['notes'])
        self.add_grave(graves['notes'], REM_NOTE,latest_usn)

        # since level 0 deck ,we only remove deck ,but backend will delete child,it is ok, the delete
        # will have once effect
        self.col.decks.remove(graves['decks']) 
        self.add_grave(graves['decks'], REM_DECK,latest_usn)

    # Models
    ##########################################################################

    def getModels(self):
        mods = [m for m in self.col.models.all() if m['usn'] == -1]
        for m in mods:
            m['usn'] = self.maxUsn
        self.col.models.save()
        return mods

    def mergeModels(self, rchg):
        for r in rchg:
            l = self.col.models.get(r['id'])
            # if missing locally or server is newer, update
            if not l or r['mod'] > l['mod']:
                self.col.models.update(r)

    # Decks
    ##########################################################################

    def getDecks(self):
        decks = [g for g in self.col.decks.all() if g['usn'] == -1]
        for g in decks:
            g['usn'] = self.maxUsn
        dconf = [g for g in self.col.decks.allConf() if g['usn'] == -1]
        for g in dconf:
            g['usn'] = self.maxUsn
        self.col.decks.save()
        return [decks, dconf]

    def mergeDecks(self, rchg):
        for r in rchg[0]:
            l = self.col.decks.get(r['id'], False)
            # work around mod time being stored as string
            if l and not isinstance(l['mod'], int):
                l['mod'] = int(l['mod'])

            # if missing locally or server is newer, update
            if not l or r['mod'] > l['mod']:
                self.col.decks.update(r)
        for r in rchg[1]:
            try:
                l = self.col.decks.getConf(r['id'])
            except KeyError:
                l = None
            # if missing locally or server is newer, update
            if not l or r['mod'] > l['mod']:
                self.col.decks.updateConf(r)

    # Tags
    ##########################################################################
    def allItems(self) -> List[Tuple[str, int]]:
        tags=self.col.db.execute("select tag, usn from tags")
        return [(tag, int(usn)) for tag,usn in tags]
    def getTags(self):
        tags = []
        for t, usn in self.allItems():
            if usn == -1:
                self.col.tags.tags[t] = self.maxUsn
                tags.append(t)
        self.col.tags.save()
        return tags

    def mergeTags(self, tags):
        self.col.tags.register(tags, usn=self.maxUsn)

    # Cards/notes/revlog
    ##########################################################################

    def mergeRevlog(self, logs):
        self.col.db.executemany(
            "insert or ignore into revlog values (?,?,?,?,?,?,?,?,?)",
            logs)

    def newerRows(self, data, table, modIdx):
        ids = (r[0] for r in data)
        lmods = {}
        for id, mod in self.col.db.execute(
            "select id, mod from %s where id in %s and %s" % (
                table, ids2str(ids), self.usnLim())):
            lmods[id] = mod
        update = []
        for r in data:
            if r[0] not in lmods or lmods[r[0]] < r[modIdx]:
                update.append(r)
        # replace col.log by just using print
        print(table, data)
        return update

    def mergeCards(self, cards):
        self.col.db.executemany(
            "insert or replace into cards values "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            self.newerRows(cards, "cards", 4))

    def mergeNotes(self, notes):
        rows = self.newerRows(notes, "notes", 3)
        self.col.db.executemany(
            "insert or replace into notes values (?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        self.col.after_note_updates([f[0] for f in rows], mark_modified=False, generate_cards=False)

    # Col config
    ##########################################################################

    def getConf(self):
        return self.col.conf

    def mergeConf(self, conf):
        for key, value in conf.items():
            self.col.set_config(key, value)
#         self.col.backend.set_all_config(json.dumps(conf).encode())

# Wrapper for requests that tracks upload/download progress
##########################################################################

class AnkiRequestsClient(object):
    verify = True
    timeout = 60

    def __init__(self):
        self.session = requests.Session()

    def post(self, url, data, headers):
        data = _MonitoringFile(data)
        headers['User-Agent'] = self._agentName()
        return self.session.post(
            url, data=data, headers=headers, stream=True, timeout=self.timeout, verify=self.verify)

    def get(self, url, headers=None):
        if headers is None:
            headers = {}
        headers['User-Agent'] = self._agentName()
        return self.session.get(url, stream=True, headers=headers, timeout=self.timeout, verify=self.verify)

    def streamContent(self, resp):
        resp.raise_for_status()

        buf = io.BytesIO()
        for chunk in resp.iter_content(chunk_size=HTTP_BUF_SIZE):
            buf.write(chunk)
        return buf.getvalue()

    def _agentName(self):
        from anki import version
        return "Anki {}".format(version)

# allow user to accept invalid certs in work/school settings
if os.environ.get("ANKI_NOVERIFYSSL"):
    AnkiRequestsClient.verify = False

    import warnings
    warnings.filterwarnings("ignore")

class _MonitoringFile(io.BufferedReader):
    def read(self, size=-1):
        data = io.BufferedReader.read(self, HTTP_BUF_SIZE)

        return data

# HTTP syncing tools
##########################################################################

class HttpSyncer(object):
    def __init__(self, hkey=None, client=None, hostNum=None):
        self.hkey = hkey
        self.skey = checksum(str(random.random()))[:8]
        self.client = client or AnkiRequestsClient()
        self.postVars = {}
        self.hostNum = hostNum
        self.prefix = "sync/"

    def syncURL(self):
        if devMode:
            url = "https://l1sync.ankiweb.net/"
        else:
            url = SYNC_BASE % (self.hostNum or "")
        return url + self.prefix

    def assertOk(self, resp):
        # not using raise_for_status() as aqt expects this error msg
        if resp.status_code != 200:
            raise Exception("Unknown response code: %s" % resp.status_code)

    # Posting data as a file
    ######################################################################
    # We don't want to post the payload as a form var, as the percent-encoding is
    # costly. We could send it as a raw post, but more HTTP clients seem to
    # support file uploading, so this is the more compatible choice.

    def _buildPostData(self, fobj, comp):
        BOUNDARY=b"Anki-sync-boundary"
        bdry = b"--"+BOUNDARY
        buf = io.BytesIO()
        # post vars
        self.postVars['c'] = 1 if comp else 0
        for (key, value) in list(self.postVars.items()):
            buf.write(bdry + b"\r\n")
            buf.write(
                ('Content-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' %
                (key, value)).encode("utf8"))
        # payload as raw data or json
        rawSize = 0
        if fobj:
            # header
            buf.write(bdry + b"\r\n")
            buf.write(b"""\
Content-Disposition: form-data; name="data"; filename="data"\r\n\
Content-Type: application/octet-stream\r\n\r\n""")
            # write file into buffer, optionally compressing
            if comp:
                tgt = gzip.GzipFile(mode="wb", fileobj=buf, compresslevel=comp)
            else:
                tgt = buf
            while 1:
                data = fobj.read(65536)
                if not data:
                    if comp:
                        tgt.close()
                    break
                rawSize += len(data)
                tgt.write(data)
            buf.write(b"\r\n")
        buf.write(bdry + b'--\r\n')
        size = buf.tell()
        # connection headers
        headers = {
            'Content-Type': 'multipart/form-data; boundary=%s' % BOUNDARY.decode("utf8"),
            'Content-Length': str(size),
        }
        buf.seek(0)

        if size >= 100*1024*1024 or rawSize >= 250*1024*1024:
            raise Exception("Collection too large to upload to AnkiWeb.")

        return headers, buf

    def req(self, method, fobj=None, comp=6, badAuthRaises=True):
        headers, body = self._buildPostData(fobj, comp)

        r = self.client.post(self.syncURL()+method, data=body, headers=headers)
        if not badAuthRaises and r.status_code == 403:
            return False
        self.assertOk(r)

        buf = self.client.streamContent(r)
        return buf

# Incremental sync over HTTP
######################################################################

class RemoteServer(HttpSyncer):
    def __init__(self, hkey, hostNum):
        super().__init__(self, hkey, hostNum=hostNum)

    def hostKey(self, user, pw):
        "Returns hkey or none if user/pw incorrect."
        self.postVars = dict()
        ret = self.req(
            "hostKey", io.BytesIO(json.dumps(dict(u=user, p=pw)).encode("utf8")),
            badAuthRaises=False)
        if not ret:
            # invalid auth
            return
        self.hkey = json.loads(ret.decode("utf8"))['key']
        return self.hkey

    def meta(self):
        self.postVars = dict(
            k=self.hkey,
            s=self.skey,
        )
        ret = self.req(
            "meta", io.BytesIO(json.dumps(dict(
                v=SYNC_VER, cv="ankidesktop,%s,%s"%(versionWithBuild(), platDesc()))).encode("utf8")),
            badAuthRaises=False)
        if not ret:
            # invalid auth
            return
        return json.loads(ret.decode("utf8"))

    def applyGraves(self, **kw):
        return self._run("applyGraves", kw)

    def applyChanges(self, **kw):
        return self._run("applyChanges", kw)

    def start(self, **kw):
        return self._run("start", kw)

    def chunk(self, **kw):
        return self._run("chunk", kw)

    def applyChunk(self, **kw):
        return self._run("applyChunk", kw)

    def sanityCheck2(self, **kw):
        return self._run("sanityCheck2", kw)

    def finish(self, **kw):
        return self._run("finish", kw)

    def abort(self, **kw):
        return self._run("abort", kw)

    def _run(self, cmd, data):
        return json.loads(
            self.req(cmd, io.BytesIO(json.dumps(data).encode("utf8"))).decode("utf8"))

# Full syncing
##########################################################################

class FullSyncer(HttpSyncer):
    def __init__(self, col, hkey, client, hostNum):
        super().__init__(self, hkey, client, hostNum=hostNum)
        self.postVars = dict(
            k=self.hkey,
            v="ankidesktop,%s,%s"%(anki.version, platDesc()),
        )
        self.col = col

    def download(self):
        localNotEmpty = self.col.db.scalar("select 1 from cards")
        self.col.close()
        cont = self.req("download")
        tpath = self.col.path + ".tmp"
        if cont == "upgradeRequired":
            return
        open(tpath, "wb").write(cont)
        # check the received file is ok
        d = DB(tpath)
        assert d.scalar("pragma integrity_check") == "ok"
        remoteEmpty = not d.scalar("select 1 from cards")
        d.close()
        # accidental clobber?
        if localNotEmpty and remoteEmpty:
            os.unlink(tpath)
            return "downloadClobber"
        # overwrite existing collection
        os.unlink(self.col.path)
        os.rename(tpath, self.col.path)
        self.col = None

    def upload(self):
        "True if upload successful."
        # make sure it's ok before we try to upload
        if self.col.db.scalar("pragma integrity_check") != "ok":
            return False
        if not self.basicCheck():
            return False
        # apply some adjustments, then upload
        self.col.beforeUpload()
        if self.req("upload", open(self.col.path, "rb")) != b"OK":
            return False
        return True

# Remote media syncing
##########################################################################

class RemoteMediaServer(HttpSyncer):
    def __init__(self, col, hkey, client, hostNum):
        self.col = col
        super().__init__(self, hkey, client, hostNum=hostNum)
        self.prefix = "msync/"

    def begin(self):
        self.postVars = dict(
            k=self.hkey,
            v="ankidesktop,%s,%s"%(anki.version, platDesc())
        )
        ret = self._dataOnly(self.req(
            "begin", io.BytesIO(json.dumps(dict()).encode("utf8"))))
        self.skey = ret['sk']
        return ret

    # args: lastUsn
    def mediaChanges(self, **kw):
        self.postVars = dict(
            sk=self.skey,
        )
        return self._dataOnly(
            self.req("mediaChanges", io.BytesIO(json.dumps(kw).encode("utf8"))))

    # args: files
    def downloadFiles(self, **kw):
        return self.req("downloadFiles", io.BytesIO(json.dumps(kw).encode("utf8")))

    def uploadChanges(self, zip):
        # no compression, as we compress the zip file instead
        return self._dataOnly(
            self.req("uploadChanges", io.BytesIO(zip), comp=0))

    # args: local
    def mediaSanity(self, **kw):
        return self._dataOnly(
            self.req("mediaSanity", io.BytesIO(json.dumps(kw).encode("utf8"))))

    def _dataOnly(self, resp):
        resp = json.loads(resp.decode("utf8"))
        if resp['err']:
            self.col.log("error returned:%s"%resp['err'])
            raise Exception("SyncError:%s"%resp['err'])
        return resp['data']

    # only for unit tests
    def mediatest(self, cmd):
        self.postVars = dict(
            k=self.hkey,
        )
        return self._dataOnly(
            self.req("newMediaTest", io.BytesIO(
                json.dumps(dict(cmd=cmd)).encode("utf8"))))
