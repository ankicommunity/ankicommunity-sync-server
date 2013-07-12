
from webob.dec import wsgify
from webob.exc import *
from webob import Response

try:
    import simplejson as json
except ImportError:
    import json

import os, logging

__all__ = ['RestApp', 'RestHandlerBase', 'hasReturnValue', 'noReturnValue']

def hasReturnValue(func):
    func.hasReturnValue = True
    return func

def noReturnValue(func):
    func.hasReturnValue = False
    return func

class RestHandlerBase(object):
    """Parent class for single handler callbacks."""
    hasReturnValue = True
    def __call__(self, collection, data, ids):
        pass

class RestHandlerGroupBase(object):
    """Parent class for a handler group."""
    hasReturnValue = True

class _RestHandlerWrapper(RestHandlerBase):
    def __init__(self, func_name, func, hasReturnValue=True):
        self.func_name = func_name
        self.func = func
        self.hasReturnValue = hasReturnValue
    def __call__(self, *args, **kw):
        return self.func(*args, **kw)

class RestApp(object):
    """A WSGI app that implements RESTful operations on Collections, Decks and Cards."""

    handler_types = ['collection', 'deck', 'note']

    def __init__(self, data_root, allowed_hosts='*', use_default_handlers=True, collection_manager=None):
        from AnkiServer.threading import getCollectionManager

        self.data_root = os.path.abspath(data_root)
        self.allowed_hosts = allowed_hosts

        if collection_manager is not None:
            self.collection_manager = collection_manager
        else:
            self.collection_manager = getCollectionManager()

        self.handlers = {}
        for type in self.handler_types:
            self.handlers[type] = {}

        if use_default_handlers:
            self.add_handler_group('collection', CollectionHandlerGroup())
            self.add_handler_group('deck', DeckHandlerGroup())
            self.add_handler_group('note', NoteHandlerGroup())

    def _get_path(self, path):
        npath = os.path.normpath(os.path.join(self.data_root, path, 'collection.anki2'))
        if npath[0:len(self.data_root)] != self.data_root:
            # attempting to escape our data jail!
            raise HTTPBadRequest('"%s" is not a valid path/id' % path)
        return npath

    def add_handler(self, type, name, handler):
        """Adds a callback handler for a type (collection, deck, card) with a unique name.
        
         - 'type' is the item that will be worked on, for example: collection, deck, and card.

         - 'name' is a unique name for the handler that gets used in the URL.

         - 'handler' handler can be a Python method or a subclass of the RestHandlerBase class.
        """

        if self.handlers[type].has_key(name):
            raise "Handler already for %(type)s/%(name)s exists!"
        self.handlers[type][name] = handler

    def add_handler_group(self, type, group):
        """Adds several handlers for every public method on an object descended from RestHandlerGroup.
        
        This allows you to create a single class with several methods, so that you can quickly
        create a group of related handlers."""

        import inspect
        for name, method in inspect.getmembers(group, predicate=inspect.ismethod):
            if not name.startswith('_'):
                if hasattr(group, 'hasReturnValue') and not hasattr(method, 'hasReturnValue'):
                    method = _RestHandlerWrapper(group.__class__.__name__ + '.' + name, method, group.hasReturnValue)
                self.add_handler(type, name, method)

    @wsgify
    def __call__(self, req):
        if self.allowed_hosts != '*':
            try:
                remote_addr = req.headers['X-Forwarded-For']
            except KeyError:
                remote_addr = req.remote_addr
            if remote_addr != self.allowed_hosts:
                raise HTTPForbidden()

        if req.method != 'POST':
            raise HTTPMethodNotAllowed(allow=['POST'])

        # split the URL into a list of parts
        path = req.path
        if path[0] == '/':
            path = path[1:]
        parts = path.split('/')

        # pull the type and context from the URL parts
        type = None
        ids = []
        for type in self.handler_types:
            if len(parts) == 0 or parts.pop(0) != type:
                break
            if len(parts) > 0:
                ids.append(parts.pop(0))
            if len(parts) < 2:
                break
        # sanity check to make sure the URL is valid
        if type is None or len(parts) > 1 or len(ids) == 0:
            raise HTTPNotFound()

        # get the handler name
        if len(parts) == 0:
            name = 'index'
        else:
            name = parts[0]

        # get the collection path
        collection_path = self._get_path(ids[0])
        print collection_path

        # get the handler function
        try:
            handler = self.handlers[type][name]
        except KeyError:
            raise HTTPNotFound()
         
        # get if we have a return value
        hasReturnValue = True
        if hasattr(handler, 'hasReturnValue'):
            hasReturnValue = handler.hasReturnValue

        try:
            data = json.loads(req.body)
        except ValueError, e:
            logging.error(req.path+': Unable to parse JSON: '+str(e), exc_info=True)
            raise HTTPBadRequest()
        # make the keys into non-unicode strings
        data = dict([(str(k), v) for k, v in data.items()])

        # debug
        from pprint import pprint
        pprint(data)

        # run it!
        col = self.collection_manager.get_collection(collection_path)
        try:
            output = col.execute(handler, [data, ids], {}, hasReturnValue)
        except Exception, e:
            logging.error(e)
            return HTTPInternalServerError()

        if output is None:
            return Response('', content_type='text/plain')
        else:
            return Response(json.dumps(output), content_type='application/json')

class CollectionHandlerGroup(RestHandlerGroupBase):
    """Default handler group for 'collection' type."""

    def list_decks(self, col, data, ids):
        return col.decks.all()

    @noReturnValue
    def select_deck(self, col, data, ids):
        col.decks.select(data['deck_id'])

class DeckHandlerGroup(RestHandlerGroupBase):
    """Default handler group for 'deck' type."""

    def next_card(self, col, data, ids):
        deck_id = ids[1]

        col.decks.select(deck_id)
        card = col.sched.getCard()

        return card

class NoteHandlerGroup(RestHandlerGroupBase):
    """Default handler group for 'note' type."""

    def add_new(self, col, data, ids):
        # col.addNote(...)
        pass

# Our entry point
def make_app(global_conf, **local_conf):
    # setup the logger
    logging_config_file = local_conf.get('logging.config_file')
    if logging_config_file:
        # monkey patch the logging.config.SMTPHandler if necessary
        import sys
        if sys.version_info[0] == 2 and sys.version_info[1] == 5:
            import AnkiServer.logpatch

        # load the config file
        import logging.config
        logging.config.fileConfig(logging_config_file)

    return RestApp(
        data_root=local_conf.get('data_root', '.'),
        allowed_hosts=local_conf.get('allowed_hosts', '*')
    )

