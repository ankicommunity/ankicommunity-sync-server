from ankisyncd.collection import CollectionManager, get_collection_wrapper

from threading import Thread
from queue import Queue

import time, logging

def short_repr(obj, logger=logging.getLogger(), maxlen=80):
    """Like repr, but shortens strings and bytestrings if logger's logging level
    is above DEBUG. Currently shallow and very limited, only implemented for
    dicts and lists."""
    if logger.isEnabledFor(logging.DEBUG):
        return repr(obj)

    def shorten(s):
        if isinstance(s, (bytes, str)) and len(s) > maxlen:
            return s[:maxlen] + ("..." if isinstance(s, str) else b"...")
        else:
            return s

    o = obj.copy()
    if isinstance(o, dict):
        for k in o:
            o[k] = shorten(o[k])
    elif isinstance(o, list):
        for k in range(len(o)):
            o[k] = shorten(o[k])

    return repr(o)

class ThreadingCollectionWrapper:
    """Provides the same interface as CollectionWrapper, but it creates a new Thread to
    interact with the collection."""

    def __init__(self, config, path, setup_new_collection=None):
        self.path = path
        self.wrapper = get_collection_wrapper(config, path, setup_new_collection)
        self.logger = logging.getLogger("ankisyncd." + str(self))

        self._queue = Queue()
        self._thread = None
        self._running = False
        self.last_timestamp = time.time()

        self.start()

    def __str__(self):
        return "CollectionThread[{}]".format(self.wrapper.username)

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
        self.logger.info("Starting...")

        try:
            while self._running:
                func, args, kw, return_queue = self._queue.get(True)

                if hasattr(func, '__name__'):
                    func_name = func.__name__
                else:
                    func_name = func.__class__.__name__

                self.logger.info("Running %s(*%s, **%s)", func_name, short_repr(args, self.logger), short_repr(kw, self.logger))
                self.last_timestamp = time.time()

                try:
                    ret = self.wrapper.execute(func, args, kw, return_queue)
                except Exception as e:
                    self.logger.error("Unable to %s(*%s, **%s): %s",
                        func_name, repr(args), repr(kw), e, exc_info=True)
                    # we return the Exception which will be raise'd on the other end
                    ret = e

                if return_queue is not None:
                    return_queue.put(ret)
        except Exception as e:
            self.logger.error("Thread crashed! Exception: %s", e, exc_info=True)
        finally:
            self.wrapper.close()
            # clean out old thread object
            self._thread = None
            # in case we got here via an exception
            self._running = False

            self.logger.info("Stopped!")

    def start(self):
        if not self._running:
            self._running = True
            assert self._thread is None
            self._thread = Thread(target=self._run)
            self._thread.start()

    def stop(self):
        def _stop(col):
            self._running = False
        self.execute(_stop, waitForReturn=False)

    def stop_and_wait(self):
        """ Tell the thread to stop and wait for it to happen. """
        self.stop()
        if self._thread is not None:
            self._thread.join()

    #
    # Mimic the CollectionWrapper interface
    #

    def open(self):
        """Non-op. The collection will be opened on demand."""
        pass

    def close(self):
        """Closes the underlying collection without stopping the thread."""

        def _close(col):
            self.wrapper.close()
        self.execute(_close, waitForReturn=False)

    def opened(self):
        return self.wrapper.opened()

class ThreadingCollectionManager(CollectionManager):
    """Manages a set of ThreadingCollectionWrapper objects."""

    collection_wrapper = ThreadingCollectionWrapper

    def __init__(self, config):
        super(ThreadingCollectionManager, self).__init__(config)

        self.monitor_frequency = 15
        self.monitor_inactivity = 90
        self.logger = logging.getLogger("ankisyncd.ThreadingCollectionManager")

        monitor = Thread(target=self._monitor_run)
        monitor.daemon = True
        monitor.start()
        self._monitor_thread = monitor

    # TODO: we should raise some error if a collection is started on a manager that has already been shutdown!
    #       or maybe we could support being restarted?

    # TODO: it would be awesome to have a safe way to stop inactive threads completely!
    # TODO: we need a way to inform other code that the collection has been closed
    def _monitor_run(self):
        """ Monitors threads for inactivity and closes the collection on them
        (leaves the thread itself running -- hopefully waiting peacefully with only a
        small memory footprint!) """
        while True:
            cur = time.time()
            for path, thread in self.collections.items():
                if thread.running and thread.wrapper.opened() and thread.qempty() and cur - thread.last_timestamp >= self.monitor_inactivity:
                    self.logger.info("Monitor is closing collection on inactive %s", thread)
                    thread.close()
            time.sleep(self.monitor_frequency)

    def shutdown(self):
        # TODO: stop the monitor thread!

        # stop all the threads
        for path, col in list(self.collections.items()):
            del self.collections[path]
            col.stop()

        # let the parent do whatever else it might want to do...
        super(ThreadingCollectionManager, self).shutdown()

#
# For working with the global ThreadingCollectionManager:
#

collection_manager = None

def get_collection_manager(config):
    """Return the global ThreadingCollectionManager for this process."""
    global collection_manager
    if collection_manager is None:
        collection_manager = ThreadingCollectionManager(config)
    return collection_manager

def shutdown():
    """If the global ThreadingCollectionManager exists, shut it down."""
    global collection_manager
    if collection_manager is not None:
        collection_manager.shutdown()
        collection_manager = None

