
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

#from pprint import pprint

try:
    import simplejson as json
    from simplejson import JSONDecodeError
except ImportError:
    import json
    JSONDecodeError = ValueError

import os, logging

import anki.consts
import anki.lang
from anki.lang import _ as t
from anki.utils import intTime

import AnkiServer

__all__ = ['RestApp', 'RestHandlerBase', 'noReturnValue']

def noReturnValue(func):
    func.hasReturnValue = False
    return func

class RestHandlerBase(object):
    """Parent class for a handler group."""
    hasReturnValue = True

class _RestHandlerWrapper(RestHandlerBase):
    """Wrapper for functions that we can't modify."""
    def __init__(self, func_name, func, hasReturnValue=True):
        self.func_name = func_name
        self.func = func
        self.hasReturnValue = hasReturnValue
    def __call__(self, *args, **kw):
        return self.func(*args, **kw)

class RestHandlerRequest(object):
    def __init__(self, app, data, ids, session):
        self.app = app
        self.data = data
        self.ids = ids
        self.session = session

    def copy(self):
        return RestHandlerRequest(self.app, self.data.copy(), self.ids[:], self.session)

    def __eq__(self, other):
        return self.app == other.app and self.data == other.data and self.ids == other.ids and self.session == other.session

class RestApp(object):
    """A WSGI app that implements RESTful operations on Collections, Decks and Cards."""

    # Defines not only the valid handler types, but their position in the URL string
    handler_types = ['collection', ['model', 'note', 'deck', 'card']]

    def __init__(self, data_root, **kw):
        from AnkiServer.threading import getCollectionManager

        self.data_root = os.path.abspath(data_root)
        self.allowed_hosts = kw.get('allowed_hosts', '*')
        self.setup_new_collection = kw.get('setup_new_collection')
        self.hook_pre_execute = kw.get('hook_pre_execute')
        self.hook_post_execute = kw.get('hook_post_execute')

        if kw.get('collection_manager') is not None:
            self.collection_manager = kw['collection_manager']
        else:
            self.collection_manager = getCollectionManager()

        self.handlers = {}
        for type_list in self.handler_types:
            if type(type_list) is not list:
                type_list = [type_list]
            for handler_type in type_list:
                self.handlers[handler_type] = {}

        if kw.get('use_default_handlers', True):
            self.add_handler_group('collection', CollectionHandler())
            self.add_handler_group('note', NoteHandler())
            self.add_handler_group('model', ModelHandler())
            self.add_handler_group('deck', DeckHandler())
            self.add_handler_group('card', CardHandler())

        # hold per collection session data
        self.sessions = {}

    def add_handler(self, type, name, handler):
        """Adds a callback handler for a type (collection, deck, card) with a unique name.
        
         - 'type' is the item that will be worked on, for example: collection, deck, and card.

         - 'name' is a unique name for the handler that gets used in the URL.

         - 'handler' is a callable that takes (collection, data, ids).
        """

        if self.handlers[type].has_key(name):
            raise "Handler already for %(type)s/%(name)s exists!"
        self.handlers[type][name] = handler

    def add_handler_group(self, type, group):
        """Adds several handlers for every public method on an object descended from RestHandlerBase.
        
        This allows you to create a single class with several methods, so that you can quickly
        create a group of related handlers."""

        import inspect
        for name, method in inspect.getmembers(group, predicate=inspect.ismethod):
            if not name.startswith('_'):
                if hasattr(group, 'hasReturnValue') and not hasattr(method, 'hasReturnValue'):
                    method = _RestHandlerWrapper(group.__class__.__name__ + '.' + name, method, group.hasReturnValue)
                self.add_handler(type, name, method)

    def execute_handler(self, type, name, col, req):
        """Executes the handler with the given type and name, passing in the col and req as arguments."""

        handler, hasReturnValue = self._getHandler(type, name)
        ret = handler(col, req)
        if hasReturnValue:
            return ret

    def list_collections(self):
        """Returns an array of valid collection names in our self.data_path."""
        return [x for x in os.listdir(self.data_root) if os.path.exists(os.path.join(self.data_root, x, 'collection.anki2'))]

    def _checkRequest(self, req):
        """Raises an exception if the request isn't allowed or valid for some reason."""
        if self.allowed_hosts != '*':
            try:
                remote_addr = req.headers['X-Forwarded-For']
            except KeyError:
                remote_addr = req.remote_addr
            if remote_addr != self.allowed_hosts:
                raise HTTPForbidden()
        
        if req.path == '/':
            if req.method != 'GET':
                raise HTTPMethodNotAllowed(allow=['GET'])
        elif req.method != 'POST':
            raise HTTPMethodNotAllowed(allow=['POST'])

    def _parsePath(self, path):
        """Takes a request path and returns a tuple containing the handler type, name
        and a list of ids.

        Raises an HTTPNotFound exception if the path is invalid."""

        if path in ('', '/'):
            raise HTTPNotFound()

        # split the URL into a list of parts
        if path[0] == '/':
            path = path[1:]
        parts = path.split('/')

        # pull the type and context from the URL parts
        handler_type = None
        ids = []
        for type_list in self.handler_types:
            if len(parts) == 0:
                break

            # some URL positions can have multiple types
            if type(type_list) is not list:
                type_list = [type_list]

            # get the handler_type
            if parts[0] not in type_list:
                break
            handler_type = parts.pop(0)

            # add the id to the id list
            if len(parts) > 0:
                ids.append(parts.pop(0))
            # break if we don't have enough parts to make a new type/id pair
            if len(parts) < 2:
                break

        # sanity check to make sure the URL is valid
        if len(parts) > 1 or len(ids) == 0:
            raise HTTPNotFound()

        # get the handler name
        if len(parts) == 0:
            name = 'index'
        else:
            name = parts[0]

        return (handler_type, name, ids)

    def _getCollectionPath(self, collection_id):
        """Returns the path to the collection based on the collection_id from the request.
        
        Raises HTTPBadRequest if the collection_id is invalid."""

        path = os.path.normpath(os.path.join(self.data_root, collection_id, 'collection.anki2'))
        if path[0:len(self.data_root)] != self.data_root:
            # attempting to escape our data jail!
            raise HTTPBadRequest('"%s" is not a valid collection' % collection_id)

        return path

    def _getHandler(self, type, name):
        """Returns a tuple containing handler function for this type and name, and a boolean flag
        if that handler has a return value.

        Raises an HTTPNotFound exception if the handler doesn't exist."""

        # get the handler function
        try:
            handler = self.handlers[type][name]
        except KeyError:
            raise HTTPNotFound()
         
        # get if we have a return value
        hasReturnValue = True
        if hasattr(handler, 'hasReturnValue'):
            hasReturnValue = handler.hasReturnValue

        return (handler, hasReturnValue)

    def _parseRequestBody(self, req):
        """Parses the request body (JSON) into a Python dict and returns it.

        Raises an HTTPBadRequest exception if the request isn't valid JSON."""
        
        try:
            data = json.loads(req.body)
        except JSONDecodeError, e:
            logging.error(req.path+': Unable to parse JSON: '+str(e), exc_info=True)
            raise HTTPBadRequest()

        # fix for a JSON encoding 'quirk' in PHP
        if type(data) == list and len(data) == 0:
            data = {}

        # make the keys into non-unicode strings
        data = dict([(str(k), v) for k, v in data.items()])

        return data

    def _execute_handler(self, col, req, handler):
        if self.hook_pre_execute is not None:
            self.hook_pre_execute(col, req)
        result = handler(col, req)
        if self.hook_post_execute is not None:
            self.hook_post_execute(col, req, result)
        return result

    @wsgify
    def __call__(self, req):
        # make sure the request is valid
        self._checkRequest(req)

        # special non-collection paths
        if req.path == '/':
            return Response('AnkiServer ' + str(AnkiServer.__version__), content_type='text/plain')
        if req.path == '/list_collections':
            return Response(json.dumps(self.list_collections()), content_type='application/json')

        # parse the path
        type, name, ids = self._parsePath(req.path)

        # get the collection path
        collection_path = self._getCollectionPath(ids[0])
        print collection_path

        # get the handler function
        handler, hasReturnValue = self._getHandler(type, name)

        # parse the request body
        data = self._parseRequestBody(req)

        # get the users session
        try:
            session = self.sessions[ids[0]]
        except KeyError:
            session = self.sessions[ids[0]] = {}

        # debug
        from pprint import pprint
        pprint(data)

        # run it!
        try:
            col = self.collection_manager.get_collection(collection_path, self.setup_new_collection)
            handler_request = RestHandlerRequest(self, data, ids, session)
            output = col.execute(self._execute_handler, [handler_request, handler], {}, hasReturnValue)
        except HTTPError, e:
            # we pass these on through!
            raise
        except Exception, e:
            logging.error(e)
            return HTTPInternalServerError()

        if output is None:
            return Response('', content_type='text/plain')
        else:
            return Response(json.dumps(output), content_type='application/json')

class CollectionHandler(RestHandlerBase):
    """Default handler group for 'collection' type."""
    
    #
    # MODELS - Store fields definitions and templates for notes
    #

    def list_models(self, col, req):
        # This is already a list of dicts, so it doesn't need to be serialized
        return col.models.all()

    def find_model_by_name(self, col, req):
        # This is already a list of dicts, so it doesn't need to be serialized
        return col.models.byName(req.data['model'])

    #
    # NOTES - Information (in fields per the model) that can generate a card
    #         (based on a template from the model).
    #

    def find_notes(self, col, req):
        query = req.data.get('query', '')
        ids = col.findNotes(query)

        if req.data.get('preload', False):
            notes = [NoteHandler._serialize(col.getNote(id)) for id in ids]
        else:
            notes = [{'id': id} for id in ids]

        return notes

    def latest_notes(self, col, req):
        # TODO: use SQLAlchemy objects to do this
        sql = "SELECT n.id FROM notes AS n";
        args = []
        if req.data.has_key('updated_since'):
            sql += ' WHERE n.mod > ?'
            args.append(req.data['updated_since'])
        sql += ' ORDER BY n.mod DESC'
        sql += ' LIMIT ' + str(req.data.get('limit', 10))
        ids = col.db.list(sql, *args)

        if req.data.get('preload', False):
            notes = [NoteHandler._serialize(col.getNote(id)) for id in ids]
        else:
            notes = [{'id': id} for id in ids]

        return notes

    @noReturnValue
    def add_note(self, col, req):
        from anki.notes import Note

        # TODO: I think this would be better with 'model' for the name
        # and 'mid' for the model id.
        if type(req.data['model']) in (str, unicode):
            model = col.models.byName(req.data['model'])
        else:
            model = col.models.get(req.data['model'])

        note = Note(col, model)
        for name, value in req.data['fields'].items():
            note[name] = value

        if req.data.has_key('tags'):
            note.setTagsFromStr(req.data['tags'])

        col.addNote(note)

    def list_tags(self, col, req):
        return col.tags.all()

    #
    # DECKS - Groups of cards
    #

    def list_decks(self, col, req):
        # This is already a list of dicts, so it doesn't need to be serialized
        return col.decks.all()

    @noReturnValue
    def select_deck(self, col, req):
        deck = DeckHandler._get_deck(col, req.data['deck'])
        col.decks.select(deck['id'])

    dyn_modes = {
        'random': anki.consts.DYN_RANDOM,
        'added': anki.consts.DYN_ADDED,
        'due': anki.consts.DYN_DUE,
    }

    def create_dynamic_deck(self, col, req):
        name = req.data.get('name', t('Custom Study Session'))
        deck = col.decks.byName(name)
        if deck:
            if not deck['dyn']:
                raise HTTPBadRequest("There is an existing non-dynamic deck with the name %s" % name)
            
            # safe to empty it because it's a dynamic deck
            # TODO: maybe this should be an option?
            col.sched.emptyDyn(deck['id'])
        else:
            deck = col.decks.get(col.decks.newDyn(name))

        query = req.data.get('query', '')
        count = int(req.data.get('count', 100))
        mode = req.data.get('mode', 'random') 

        try:
            mode = self.dyn_modes[mode]
        except KeyError:
            raise HTTPBadRequest("Unknown mode: %s" % mode)

        deck['terms'][0] = [query, count, mode]

        if mode != anki.consts.DYN_RANDOM:
            deck['resched'] = True
        else:
            deck['resched'] = False

        if not col.sched.rebuildDyn(deck['id']):
            raise HTTPBadRequest("No cards matched the criteria you provided")

        col.decks.save(deck)
        col.sched.reset()

        return deck

    def empty_dynamic_deck(self, col, req):
        name = req.data.get('name', t('Custom Study Session'))
        deck = col.decks.byName(name)

        if not deck:
            raise HTTPBadRequest("Cannot find a deck with the given name: %s" % name)

        if not deck['dyn']:
            raise HTTPBadRequest("The given deck is not dynamic: %s" % name)
            
        col.sched.emptyDyn(deck['id'])

    #
    # CARD - A specific card in a deck with a history of review (generated from
    #        a note based on the template).
    #

    def find_cards(self, col, req):
        from AnkiServer.find import Finder

        query = req.data.get('query', '')
        order = req.data.get('order', False)

        # TODO: patch Anki to support limit/offset and then remove this crazy hack!
        finder = Finder(col)
        finder.limit = int(req.data.get('limit', 0))
        finder.offset = int(req.data.get('offset', 0))
        ids = finder.findCards(query, order)

        if req.data.get('preload', False):
            cards = [CardHandler._serialize(col.getCard(id), req.data) for id in ids]
        else:
            cards = [{'id': id} for id in ids]

        return cards

    def latest_cards(self, col, req):
        # TODO: use SQLAlchemy objects to do this
        sql = "SELECT c.id FROM notes AS n INNER JOIN cards AS c ON c.nid = n.id";
        args = []
        if req.data.has_key('updated_since'):
            sql += ' WHERE n.mod > ?'
            args.append(req.data['updated_since'])
        sql += ' ORDER BY n.mod DESC'
        sql += ' LIMIT ' + str(req.data.get('limit', 10))
        ids = col.db.list(sql, *args)

        if req.data.get('preload', False):
            cards = [CardHandler._serialize(col.getCard(id), req.data) for id in ids]
        else:
            cards = [{'id': id} for id in ids]

        return cards

    #
    # SCHEDULER - Controls card review, ie. intervals, what cards are due, answering a card, etc.
    #

    def reset_scheduler(self, col, req):
        if req.data.has_key('deck'):
            deck = DeckHandler._get_deck(col, req.data['deck'])
            col.decks.select(deck['id'])

        col.sched.reset()
        counts = col.sched.counts()
        return {
            'new_cards': counts[0],
            'learning_cards': counts[1],
            'review_cards': counts[1],
        }

    def extend_scheduler_limits(self, col, req):
        new_cards = int(req.data.get('new_cards', 0))
        review_cards = int(req.data.get('review_cards', 0))
        col.sched.extendLimits(new_cards, review_cards)
        col.sched.reset()

    button_labels = ['Easy', 'Good', 'Hard']

    def _get_answer_buttons(self, col, card):
        l = []

        # Put the correct number of buttons
        cnt = col.sched.answerButtons(card)
        for idx in range(0, cnt - 1):
            l.append(self.button_labels[idx])
        l.append('Again')
        l.reverse()

        # Loop through and add the ease, estimated time (in seconds) and other info
        return [{
          'ease': ease,
          'label': label,
          'string_label': t(label),
          'interval': col.sched.nextIvl(card, ease),
          'string_interval': col.sched.nextIvlStr(card, ease),
        } for ease, label in enumerate(l, 1)]

    def next_card(self, col, req):
        if req.data.has_key('deck'):
            deck = DeckHandler._get_deck(col, req.data['deck'])
            col.decks.select(deck['id'])

        card = col.sched.getCard()
        if card is None:
            return None

        # put it into the card cache to be removed when we answer it
        #if not req.session.has_key('cards'):
        #    req.session['cards'] = {}
        #req.session['cards'][long(card.id)] = card

        card.startTimer()

        result = CardHandler._serialize(card, req.data)
        result['answer_buttons'] = self._get_answer_buttons(col, card)

        return result

    # TODO: calling answer_card() when the scheduler is not setup can 
    #       be an error! This can happen after a collection has been closed
    #       for inactivity, and opened later. But since we're using
    #       @noReturnValue, no error will be passed up. :-/ What to do?
    @noReturnValue
    def answer_card(self, col, req):
        import time

        card_id = long(req.data['id'])
        ease = int(req.data['ease'])

        card = col.getCard(card_id)
        if req.data.has_key('timerStarted'):
            card.timerStarted = float(req.data['timerStarted'])
        else:
            card.timerStarted = time.time()

        col.sched.answerCard(card, ease)

    @noReturnValue
    def suspend_cards(self, col, req):
        card_ids = req.data['ids']
        col.sched.suspendCards(card_ids)

    @noReturnValue
    def unsuspend_cards(self, col, req):
        card_ids = req.data['ids']
        col.sched.unsuspendCards(card_ids)

    def cards_recent_ease(self, col, req):
        """Returns the most recent ease for each card."""

        # TODO: Use sqlalchemy to build this query!
        sql = "SELECT r.cid, r.ease, r.id FROM revlog AS r INNER JOIN (SELECT cid, MAX(id) AS id FROM revlog GROUP BY cid) AS q ON r.cid = q.cid AND r.id = q.id"
        where = []
        if req.data.has_key('ids'):
            where.append('ids IN (' + (','.join(["'%s'" % x for x in req.data['ids']])) + ')')
        if len(where) > 0:
            sql += ' WHERE ' + ' AND '.join(where)

        result = []
        for r in col.db.all(sql):
            result.append({'id': r[0], 'ease': r[1], 'timestamp': int(r[2] / 1000)})

        return result

    def latest_revlog(self, col, req):
        """Returns recent entries from the revlog."""

        # TODO: Use sqlalchemy to build this query!
        sql = "SELECT r.id, r.ease, r.cid, r.usn, r.ivl, r.lastIvl, r.factor, r.time, r.type FROM revlog AS r"
        args = []
        if req.data.has_key('updated_since'):
            sql += ' WHERE r.id > ?'
            args.append(long(req.data['updated_since']) * 1000)
        sql += ' ORDER BY r.id DESC'
        sql += ' LIMIT ' + str(req.data.get('limit', 100))

        revlog = col.db.all(sql, *args)
        return [{
            'id': r[0],
            'ease': r[1],
            'timestamp': int(r[0] / 1000),
            'card_id': r[2],
            'usn': r[3],
            'interval': r[4],
            'last_interval': r[5],
            'factor': r[6],
            'time': r[7],
            'type': r[8],
        } for r in revlog]

    stats_reports = {
      'today': 'todayStats',
      'due': 'dueGraph',
      'reps': 'repsGraph',
      'interval': 'ivlGraph',
      'hourly': 'hourGraph',
      'ease': 'easeGraph',
      'card': 'cardGraph',
      'footer': 'footer',
    }
    stats_reports_order = ['today', 'due', 'reps', 'interval', 'hourly', 'ease', 'card', 'footer']

    def stats_report(self, col, req):
        import anki.stats
        import re

        stats = anki.stats.CollectionStats(col)
        stats.width = int(req.data.get('width', 600))
        stats.height = int(req.data.get('height', 200))
        reports = req.data.get('reports', self.stats_reports_order)
        include_css = req.data.get('include_css', False)
        include_jquery = req.data.get('include_jquery', False)
        include_flot = req.data.get('include_flot', False)

        if include_css:
            from anki.statsbg import bg
            html = stats.css % bg
        else:
            html = ''

        for name in reports:
            if not self.stats_reports.has_key(name):
                raise HTTPBadRequest("Unknown report name: %s" % name)
            func = getattr(stats, self.stats_reports[name])

            html += '<div class="anki-graph anki-graph-%s">' % name
            html += func()
            html += '</div>'

        # fix an error in some inline styles
        # TODO: submit a patch to Anki!
        html = re.sub(r'style="width:([0-9\.]+); height:([0-9\.]+);"', r'style="width:\1px; height: \2px;"', html)
        html = re.sub(r'-webkit-transform: ([^;]+);', r'-webkit-transform: \1; -moz-transform: \1; -ms-transform: \1; -o-transform: \1; transform: \1;', html)

        scripts = []
        if include_jquery or include_flot:
            import anki.js
            if include_jquery:
                scripts.append(anki.js.jquery)
            if include_flot:
                scripts.append(anki.js.plot)
        if len(scripts) > 0:
            html = "<script>%s\n</script>" % ''.join(scripts) + html

        return html

    #
    # GLOBAL / MISC
    #

    @noReturnValue
    def set_language(self, col, req):
        anki.lang.setLang(req.data['code'])

class ImportExportHandler(RestHandlerBase):
    """Handler group for the 'collection' type, but it's not added by default."""

    def _get_filedata(self, data):
        import urllib2

        if data.has_key('data'):
            return data['data']

        fd = None
        try:
            fd = urllib2.urlopen(data['url'])
            filedata = fd.read()
        finally:
            if fd is not None:
                fd.close()

        return filedata

    def _get_importer_class(self, data):
        filetype = data['filetype']

        from AnkiServer.importer import get_importer_class
        importer_class = get_importer_class(filetype)
        if importer_class is None:
            raise HTTPBadRequest("Unknown filetype '%s'" % filetype)

        return importer_class

    def import_file(self, col, req):
        import AnkiServer.importer
        import tempfile

        # get the importer class
        importer_class = self._get_importer_class(req.data)

        # get the file data
        filedata = self._get_filedata(req.data)

        # write the file data to a temporary file
        try:
            path = None
            with tempfile.NamedTemporaryFile('wt', delete=False) as fd:
                path = fd.name
                fd.write(filedata)

            AnkiServer.importer.import_file(importer_class, col, path)
        finally:
            if path is not None:
                os.unlink(path)

class ModelHandler(RestHandlerBase):
    """Default handler group for 'model' type."""

    def field_names(self, col, req):
        model = col.models.get(req.ids[1])
        if model is None:
            raise HTTPNotFound()
        return col.models.fieldNames(model)

class NoteHandler(RestHandlerBase):
    """Default handler group for 'note' type."""

    @staticmethod
    def _serialize(note):
        d = {
            'id': note.id,
            'guid': note.guid,
            'model': note.model(),
            'mid': note.mid,
            'mod': note.mod,
            'scm': note.scm,
            'tags': note.tags,
            'string_tags': ' '.join(note.tags),
            'fields': {},
            'flags': note.flags,
            'usn': note.usn,
        }

        # add all the fields
        for name, value in note.items():
            d['fields'][name] = value

        return d

    def index(self, col, req):
        note = col.getNote(req.ids[1])
        return self._serialize(note)

    def update(self, col, req):
        note = col.getNote(req.ids[1])
        if note:
            # update fields
            for name in note.keys():
                note[name] = req.data['fields'].get(name, '')

            # update tags
            note.tags = req.data['tags']

            # optionally, we can prevent note.mod from getting updated -
            # this is useful when adding the 'marked' tag or other changes
            # we don't want to really "count"
            if req.data.get('update_mod', True):
                mod = intTime()
            else:
                mod = note.mod

            note.flush(mod)

    def delete(self, col, req):
        col.remNotes([req.ids[1]])

    @noReturnValue
    def add_tags(self, col, req):
        note = col.getNote(req.ids[1])

        # optionally, we can prevent note.mod from getting updated -
        # this is useful when adding the 'marked' tag or other changes
        # we don't want to really "count"
        if req.data.get('update_mod', True):
            mod = intTime()
        else:
            mod = note.mod

        for tag in req.data['tags']:
            note.addTag(tag)

        note.flush(mod)

    @noReturnValue
    def remove_tags(self, col, req):
        note = col.getNote(req.ids[1])

        # optionally, we can prevent note.mod from getting updated -
        # this is useful when adding the 'marked' tag or other changes
        # we don't want to really "count"
        if req.data.get('update_mod', True):
            mod = intTime()
        else:
            mod = note.mod

        for tag in req.data['tags']:
            note.delTag(tag)

        note.flush(mod)

class DeckHandler(RestHandlerBase):
    """Default handler group for 'deck' type."""

    @staticmethod
    def _get_deck(col, val):
        try:
            did = long(val)
            deck = col.decks.get(did, False)
        except ValueError:
            deck = col.decks.byName(val)

        if deck is None:
            raise HTTPNotFound('No deck with id or name: ' + str(val))

        return deck

    def index(self, col, req):
        return self._get_deck(col, req.ids[1])
    
    def next_card(self, col, req):
        req_copy = req.copy()
        req_copy.data['deck'] = req.ids[1]
        del req_copy.ids[1]

        # forward this to the CollectionHandler
        return req.app.execute_handler('collection', 'next_card', col, req_copy)

    def get_conf(self, col, req):
        # TODO: should probably live in a ConfHandler
        return col.decks.confForDid(req.ids[1])

    @noReturnValue
    def set_update_conf(self, col, req):
        data = req.data.copy()
        del data['id']

        conf = col.decks.confForDid(req.ids[1])
        conf = conf.copy()
        conf.update(data)

        col.decks.updateConf(conf)

class CardHandler(RestHandlerBase):
    """Default handler group for 'card' type."""

    @staticmethod
    def _serialize(card, opts):
        d = {
            'id': card.id,
            'isEmpty': card.isEmpty(),
            'css': card.css(),
            'question': card._getQA()['q'],
            'answer': card._getQA()['a'],
            'did': card.did,
            'due': card.due,
            'factor': card.factor,
            'ivl': card.ivl,
            'lapses': card.lapses,
            'left': card.left,
            'mod': card.mod,
            'nid': card.nid,
            'odid': card.odid,
            'odue': card.odue,
            'ord': card.ord,
            'queue': card.queue,
            'reps': card.reps,
            'type': card.type,
            'usn': card.usn,
            'timerStarted': card.timerStarted,
        }

        if opts.get('load_note', False):
            d['note'] = NoteHandler._serialize(card.col.getNote(card.nid))

        if opts.get('load_deck', False):
            d['deck'] = card.col.decks.get(card.did)

        if opts.get('load_latest_revlog', False):
            d['latest_revlog'] = CardHandler._latest_revlog(card.col, card.id)

        return d

    @staticmethod
    def _latest_revlog(col, card_id):
        r = col.db.first("SELECT r.id, r.ease FROM revlog AS r WHERE r.cid = ? ORDER BY id DESC LIMIT 1", card_id)
        if r:
            return {'id': r[0], 'ease': r[1], 'timestamp': int(r[0] / 1000)}

    def index(self, col, req):
        card = col.getCard(req.ids[1])
        return self._serialize(card, req.data)

    def _forward_to_note(self, col, req, name):
        card = col.getCard(req.ids[1])

        req_copy = req.copy()
        req_copy.ids[1] = card.nid

        return req.app.execute_handler('note', name, col, req)

    @noReturnValue
    def add_tags(self, col, req):
        self._forward_to_note(col, req, 'add_tags')

    @noReturnValue
    def remove_tags(self, col, req):
        self._forward_to_note(col, req, 'remove_tags')

    def stats_report(self, col, req):
        card = col.getCard(req.ids[1])
        return col.cardStats(card)

    def latest_revlog(self, col, req):
        return self._latest_revlog(col, req.ids[1])

# Our entry point
def make_app(global_conf, **local_conf):
    # TODO: we should setup the default language from conf!

    # setup the logger
    from AnkiServer.utils import setup_logging
    setup_logging(local_conf.get('logging.config_file'))

    return RestApp(
        data_root=local_conf.get('data_root', '.'),
        allowed_hosts=local_conf.get('allowed_hosts', '*')
    )

