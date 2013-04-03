
from webob.dec import wsgify
from webob.exc import *
from webob import Response

import anki
from anki.facts import Fact
from anki.models import Model, CardModel, FieldModel

from threading import Thread
from Queue import Queue

try:
    import simplejson as json
except ImportError:
    import json

import os, errno, time, logging

__all__ = ['DeckThread']

def ExternalModel():
    m = Model(u'External')
    # we can only guarantee that the Front will be unique because it will
    # be based on the headword, language, pos.  The Back could be anything!
    m.addFieldModel(FieldModel(u'Front', True, True))
    # while I think that Back should be required, I don't really want this to
    # fail just because of that!!
    m.addFieldModel(FieldModel(u'Back', False, False))
    m.addFieldModel(FieldModel(u'External ID', True, True))

    front = u'<span style="font-family: Arial; font-size: 20px; color: #000000; white-space: pre-wrap;">{{{Front}}}</span>'
    back = u'<span style="font-family: Arial; font-size: 20px; color: #000000; white-space: pre-wrap;">{{{Back}}}</span>'
    m.addCardModel(CardModel(u'Forward', front, back))
    m.addCardModel(CardModel(u'Reverse', back, front))

    m.tags = u"External"
    return m

class DeckWrapper(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._deck = None

    def _create_deck(self):
        # mkdir -p the path, because it might not exist
        dir = os.path.dirname(self.path)
        try:
            os.makedirs(dir)
        except OSError, exc:
            if exc.errno == errno.EEXIST:
                pass
            else:
                raise

        deck = anki.DeckStorage.Deck(self.path)
        try:
            deck.initUndo()
            deck.addModel(ExternalModel())
            deck.save()
        except Exception, e:
            deck.close()
            deck = None
            raise e

        return deck

    def open(self):
        if self._deck is None:
            if os.path.exists(self.path):
                self._deck = anki.DeckStorage.Deck(self.path)
            else:
                self._deck = self._create_deck()
        return self._deck

    def close(self):
        if self._deck is None:
            return

        self._deck.close()
        self._deck = None

        # delete the cache for 'External ID' on this deck
        if hasattr(self, '_external_field_id'):
            delattr(self, '_external_field_id')

    def opened(self):
        return self._deck is not None

    @property
    def external_field_id(self):
        if not hasattr(self, '_external_field_id'):
            # find a field model id for a field named "External ID"
            deck = self.open()
            self._external_field_id = deck.s.scalar("SELECT id FROM fieldModels WHERE name = :name", name=u'External ID')
        if self._external_field_id is None:
            raise HTTPBadRequest("No field model named 'External ID'")
        return self._external_field_id

    def find_fact(self, external_id):
        deck = self.open()
        return deck.s.scalar("""
            SELECT factId FROM fields WHERE fieldModelId = :fieldModelId AND
                value = :externalId""", fieldModelId=self.external_field_id, externalId=external_id)

class DeckThread(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.wrapper = DeckWrapper(path)

        self._queue = Queue()
        self._thread = None
        self._running = False
        self.last_timestamp = time.time()

    @property
    def running(self):
        return self._running

    def qempty(self):
        return self._queue.empty()

    def current(self):
        from threading import current_thread
        return current_thread() == self._thread

    def execute(self, func, args=[], kw={}, waitForReturn=True):
        """ Executes a given function on this thread with the *args and **kw.

        If 'waitForReturn' is True, then it will block until the function has
        executed and return its return value.  If False, it will return None
        immediately and the function will be executed sometime later.
        """

        if waitForReturn:
            return_queue = Queue()
        else:
            return_queue = None

        self._queue.put((func, args, kw, return_queue))

        if return_queue is not None:
            ret = return_queue.get(True)
            if isinstance(ret, Exception):
                raise ret
            return ret

    def _run(self):
        logging.info('DeckThread[%s]: Starting...', self.path)

        try:
            while self._running:
                func, args, kw, return_queue = self._queue.get(True)

                logging.info('DeckThread[%s]: Running %s(*%s, **%s)', self.path, func.func_name, repr(args), repr(kw))
                self.last_timestamp = time.time()

                try:
                    ret = func(*args, **kw)
                except Exception, e:
                    logging.error('DeckThread[%s]: Unable to %s(*%s, **%s): %s',
                        self.path, func.func_name, repr(args), repr(kw), e, exc_info=True)
                    # we return the Exception which will be raise'd on the other end
                    ret = e

                if return_queue is not None:
                    return_queue.put(ret)
        except Exception, e:
            logging.error('DeckThread[%s]: Thread crashed! Exception: %s', e, exc_info=True)
        finally:
            self.wrapper.close()
            # clean out old thread object
            self._thread = None
            # in case we got here via an exception
            self._running = False

            logging.info('DeckThread[%s]: Stopped!' % self.path)

    def start(self):
        if not self._running:
            self._running = True
            assert self._thread is None
            self._thread = Thread(target=self._run)
            self._thread.start()

    def stop(self):
        def _stop():
            self._running = False
        self.execute(_stop, waitForReturn=False)

    def stop_and_wait(self):
        """ Tell the thread to stop and wait for it to happen. """
        self.stop()
        if self._thread is not None:
            self._thread.join()

class DeckThreadPool(object):
    def __init__(self):
        self.threads = {}

        self.monitor_frequency = 15
        self.monitor_inactivity = 90

        monitor = Thread(target=self._monitor_run)
        monitor.daemon = True
        monitor.start()
        self._monitor_thread = monitor

    # TODO: it would be awesome to have a safe way to stop inactive threads completely!
    def _monitor_run(self):
        """ Monitors threads for inactivity and closes the deck on them
        (leaves the thread itself running -- hopefully waiting peacefully with only a
        small memory footprint!) """
        while True:
            cur = time.time()
            for path, thread in self.threads.items():
                if thread.running and thread.wrapper.opened() and thread.qempty() and cur - thread.last_timestamp >= self.monitor_inactivity:
                    logging.info('Monitor is closing deck on inactive DeckThread[%s]' % thread.path)
                    def closeDeck(wrapper):
                        wrapper.close()
                    thread.execute(closeDeck, [thread.wrapper], waitForReturn=False)
            time.sleep(self.monitor_frequency)

    def start(self, path):
        path = os.path.abspath(path)

        try:
            thread = self.threads[path]
        except KeyError:
            thread = self.threads[path] = DeckThread(path)

        thread.start()

        return thread

    def shutdown(self):
        for thread in self.threads.values():
            thread.stop()
        self.threads = {}

thread_pool = DeckThreadPool()

#def defer(*func, **opts):
#    def decorator(func):
#        def newFunc(*args, **kw):
#            (self, thread) = args[0:2]
#            if thread.current():
#                ret = func(*args, **kw)
#                # don't return 'ret' if this isn't a wait function, to keep the API
#                # consistent even when inside the thread itself (hopefully, help
#                # avoid weird problems in the future)
#                if opts.get('waitForReturn', True):
#                    return ret
#            else:
#                return thread.execute(func, args, kw, **opts)
#        newFunc.func_name = func.func_name
#        return newFunc
#
#    if len(func) == 1:
#        return decorator(func[0])
#    elif len(func) > 1:
#        raise TypeError
#
#    return decorator

def opts(**opts):
    def dec(func):
        func.opts = opts
        return func
    return dec

class DeckAppHandler(object):
    def __init__(self, wrapper):
        self.wrapper = wrapper

    def _output_fact(self, fact):
        res = dict(zip(fact.keys(), fact.values()))
        res['id'] = str(fact.id)
        return res

    def _output_card(self, card):
        return {
            'id': card.id,
            'question': card.question,
            'answer': card.answer,
        }

    @opts(waitForReturn=False)
    def setup(self):
        # will create the deck if it doesn't exist
        self.wrapper.open()

    @opts(waitForReturn=False)
    def add_fact(self, fields):
        fact_id = self.wrapper.find_fact(fields['External ID'])
        if fact_id is not None:
            fields['id'] = fact_id
            self.save_fact(fields)
        else:
            deck = self.wrapper.open()
            fact = deck.newFact()
            for key in fact.keys():
                fact[key] = unicode(fields[key])

            deck.addFact(fact)
            deck.save()

    @opts(waitForReturn=False)
    def save_fact(self, fact):
        deck = self.wrapper.open()
        newFact = deck.s.query(Fact).get(int(fact['id']))
        for key in newFact.keys():
            newFact[key] = fact[key]

        newFact.setModified(textChanged=True, deck=deck)
        deck.setModified()
        deck.save()

    def find_fact(self, external_id):
        factId = self.wrapper.find_fact(external_id)
        if not factId:
            # we need to signal somehow to the calling application that no such
            # deck exists, but without it being considered a "bad error".  404 is 
            # inappropriate that refers to the resource (ie. /find_fact) which is
            # here obviously.
            return None

        deck = self.wrapper.open()
        fact = deck.s.query(Fact).get(factId)
        return self._output_fact(fact)

    @opts(waitForReturn=False)
    def delete_fact(self, fact_id=None, external_id=None):
        if fact_id is None and external_id is not None:
            fact_id = self.wrapper.find_fact(external_id)
        if fact_id is not None:
            deck = self.wrapper.open()
            deck.deleteFact(int(fact_id))
            deck.save()

    def resync_facts(self, external_ids):
        from anki.facts import fieldsTable
        from sqlalchemy.sql import select, and_, not_

        deck = self.wrapper.open()

        # remove extra cards
        selectExtra = select([fieldsTable.c.factId],
            and_(
                fieldsTable.c.fieldModelId == self.wrapper.external_field_id,
                not_(fieldsTable.c.value.in_(external_ids))
            )
        )
        for factId, in deck.s.execute(selectExtra).fetchall():
            deck.deleteFact(factId)
        deck.save()

        # find ids that should be on this deck but which aren't
        missing_ids = []
        for external_id in external_ids:
            if self.wrapper.find_fact(external_id) is None:
                missing_ids.append(external_id)

        return {'missing':missing_ids}

    def get_card(self):
        deck = self.wrapper.open()
        card = deck.getCard()
        if card:
            # grab the interval strings
            intervals = []
            for i in range(1, 5):
                intervals.append(deck.nextIntervalStr(card, i))

            card = self._output_card(card)
            card['intervals'] = intervals
            card['finished'] = False
        else:
            # copied from Deck.nextDueMsg() in libanki/anki/deck.py
            newCount = deck.newCardsDueBy(deck.dueCutoff + 86400)
            newCardsTomorrow = min(newCount, deck.newCardsPerDay)
            cards = deck.cardsDueBy(deck.dueCutoff + 86400)

            card = {
                'finished': True,
                'new_count': newCardsTomorrow,
                'reviews_count': cards
            }

            # TODO: clean up a bit, now that we've finished this review

        return card

    @opts(waitForReturn=False)
    def setup_scheduler(self, name):
        deck = self.wrapper.open()
        if name == 'standard':
            deck.setupStandardScheduler()
        elif name == 'reviewEarly':
            deck.setupReviewEarlyScheduler()
        elif name == 'learnMore':
            deck.setupLearnMoreScheduler()
        deck.refreshSession()
        deck.reset()

    def get_options(self):
        deck = self.wrapper.open()

        return {
            'new_cards': {
                'cards_per_day': deck.newCardsPerDay,
                'order': deck.newCardOrder,
                'spacing': deck.newCardSpacing,
            },
            'reviews': {
                'failed_card_max': deck.failedCardMax,
                'order': deck.revCardOrder,
                'failed_policy': deck.getFailedCardPolicy(),
            }
        }

    @opts(waitForReturn=False)
    def set_options(self, study_options):
        deck = self.wrapper.open()

        # new card options
        deck.newCardsPerDay = int(study_options['new_cards']['cards_per_day'])
        deck.newCardOrder = int(study_options['new_cards']['order'])
        if deck.newCardOrder == anki.deck.NEW_CARDS_RANDOM:
            deck.randomizeNewCards()
        deck.newCardSpacing = int(study_options['new_cards']['spacing'])

        # reviews options
        deck.setFailedCardPolicy(int(study_options['reviews']['failed_policy']))
        deck.failedCardMax = int(study_options['reviews']['failed_card_max'])
        deck.revCardOrder = int(study_options['reviews']['order'])

        deck.flushMod()
        deck.reset()
        deck.save()

    def answer_card(self, card_id, ease):
        ease = int(ease)
        deck = self.wrapper.open()
        card = deck.cardFromId(card_id)
        if card:
            try:
                deck.answerCard(card, ease)
            except:
                import sys, traceback
                exc_info = sys.exc_info()
                print exc_info[1]
                print traceback.print_tb(exc_info[2])
                return False
            deck.save()
        return True

class DeckApp(object):
    """ Our WSGI app. """

    direct_operations = ['add_fact', 'save_fact', 'find_fact', 'delete_fact', 'resync_facts',
        'get_card', 'answer_card']

    def __init__(self, data_root, allowed_hosts):
        self.data_root = os.path.abspath(data_root)
        self.allowed_hosts = allowed_hosts

    def _get_path(self, path):
        npath = os.path.normpath(os.path.join(self.data_root, path))
        if npath[0:len(self.data_root)] != self.data_root:
            # attempting to escape our data jail!
            raise HTTPBadRequest('"%s" is not a valid path/id' % path)
        return npath

    @wsgify
    def __call__(self, req):
        global thread_pool

        if self.allowed_hosts != '*':
            try:
                remote_addr = req.headers['X-Forwarded-For']
            except KeyError:
                remote_addr = req.remote_addr
            if remote_addr != self.allowed_hosts:
                raise HTTPForbidden()

        if req.method != 'POST':
            raise HTTPMethodNotAllowed(allow=['POST'])

        # get the deck and function to call from the path
        func = req.path
        if func[0] == '/':
            func = func[1:]
        parts = func.split('/')
        path = '/'.join(parts[:-1])
        func = parts[-1]
        if func[0] == '_' or not hasattr(DeckAppHandler, func) or not callable(getattr(DeckAppHandler, func)):
            raise HTTPNotFound()
        thread = thread_pool.start(self._get_path(path))
        handler = DeckAppHandler(thread.wrapper)
        func = getattr(handler, func)
        try:
            opts = func.opts
        except AttributeError:
            opts = {}

        try:
            input = json.loads(req.body)
        except ValueError, e:
            logging.error(req.path+': Unable to parse JSON: '+str(e), exc_info=True)
            raise HTTPBadRequest()
        # make the keys into non-unicode strings
        input = dict([(str(k), v) for k, v in input.items()])

        # debug
        from pprint import pprint
        pprint(input)

        # run it!
        try:
            output = thread.execute(func, [], input, **opts)
        except Exception, e:
            logging.error(e)
            return HTTPInternalServerError()

        if output is None:
            return Response('', content_type='text/plain')
        else:
            return Response(json.dumps(output), content_type='application/json')

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

    return DeckApp(
        data_root=local_conf.get('data_root', '.'),
        allowed_hosts=local_conf.get('allowed_hosts', '*')
    )

