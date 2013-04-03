
import anki
import anki.storage

from threading import Thread
from Queue import Queue

try:
    import simplejson as json
except ImportError:
    import json

import os, errno, time, logging

__all__ = ['CollectionThread']

# TODO: I feel like we shouldn't need this wrapper...
class CollectionWrapper(object):
    """A simple wrapper around a collection for the purpose of opening and closing on demand
    as well as doing special initialization."""

    def __init__(self, path):
        self.path = os.path.realpath(path)
        self._col = None

    def _create_colection(self):
        # mkdir -p the path, because it might not exist
        dirname = os.path.dirname(self.path)
        try:
            os.makedirs(dirname)
        except OSError, exc:
            if exc.errno == errno.EEXIST:
                pass
            else:
                raise

        col = anki.Storage.Collection(self.path)

        # Do any special setup
        self.setup_new_collection(col)

        return col

    def setup_new_collection(self, col):
        """Override this function to initial collections in some special way."""
        pass

    def open(self):
        if self._col is None:
            if os.path.exists(self.path):
                self._col = anki.DeckStorage.Deck(self.path)
            else:
                self._deck = self._create_deck()
        return self._deck

    def close(self):
        if self._col is None:
            return

        self._col.close()
        self._col = None

    def opened(self):
        return self._col is not None

class CollectionThread(object):
    def __init__(self, path, wrapper_class=CollectionWrapper):
        self.path = os.path.realpath(path)
        self.wrapper = wrapper_class(path)

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

class CollectionThreadPool(object):
    def __init__(self, wrapper_class=CollectionWrapper):
        self.wrapper_class = wrapper_class
        self.threads = {}

        self.monitor_frequency = 15
        self.monitor_inactivity = 90

        monitor = Thread(target=self._monitor_run)
        monitor.daemon = True
        monitor.start()
        self._monitor_thread = monitor

    # TODO: it would be awesome to have a safe way to stop inactive threads completely!
    # TODO: we need a way to inform other code that the collection has been closed
    def _monitor_run(self):
        """ Monitors threads for inactivity and closes the collection on them
        (leaves the thread itself running -- hopefully waiting peacefully with only a
        small memory footprint!) """
        while True:
            cur = time.time()
            for path, thread in self.threads.items():
                if thread.running and thread.wrapper.opened() and thread.qempty() and cur - thread.last_timestamp >= self.monitor_inactivity:
                    logging.info('Monitor is closing collection on inactive CollectionThread[%s]' % thread.path)
                    def closeCollection(wrapper):
                        wrapper.close()
                    thread.execute(closeCollection, [thread.wrapper], waitForReturn=False)
            time.sleep(self.monitor_frequency)

    def create_thread(self, path):
        return CollectionThread(path, wrapper_class=self.wrapper_class)

    def start(self, path):
        path = os.path.realpath(path)

        try:
            thread = self.threads[path]
        except KeyError:
            thread = self.threads[path] = self.create_thread(path)

        thread.start()

        return thread

    def shutdown(self):
        for thread in self.threads.values():
            thread.stop()
        self.threads = {}

# TODO: There's got to be a way to do this without initializing it ALWAYS!
thread_pool = CollectionThreadPool()

