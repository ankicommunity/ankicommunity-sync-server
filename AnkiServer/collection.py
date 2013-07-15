
import anki
import anki.storage

import os, errno

__all__ = ['CollectionWrapper', 'CollectionManager']

class CollectionWrapper(object):
    """A simple wrapper around an anki.storage.Collection object.

    This allows us to manage and refer to the collection, whether it's open or not. It
    also provides a special "continuation passing" interface for executing functions
    on the collection, which makes it easy to switch to a threading mode.
    
    See ThreadingCollectionWrapper for a version that maintains a seperate thread for
    interacting with the collection.
    """

    def __init__(self, path, setup_new_collection=None):
        self.path = os.path.realpath(path)
        self.setup_new_collection = setup_new_collection
        self.__col = None

    def __del__(self):
        """Close the collection if the user forgot to do so."""
        self.close()

    def execute(self, func, args=[], kw={}, waitForReturn=True):
        """ Executes the given function with the underlying anki.storage.Collection
        object as the first argument and any additional arguments specified by *args
        and **kw.

        If 'waitForReturn' is True, then it will block until the function has
        executed and return its return value.  If False, the function MAY be
        executed some time later and None will be returned.
        """

        # Open the collection and execute the function
        self.open()
        args = [self.__col] + args
        ret = func(*args, **kw)

        # Only return the value if they requested it, so the interface remains
        # identical between this class and ThreadingCollectionWrapper
        if waitForReturn:
            return ret

    def __create_collection(self):
        """Creates a new collection and runs any special setup."""

        # mkdir -p the path, because it might not exist
        dirname = os.path.dirname(self.path)
        try:
            os.makedirs(dirname)
        except OSError, exc:
            if exc.errno == errno.EEXIST:
                pass
            else:
                raise

        col = anki.storage.Collection(self.path)

        # Do any special setup
        if self.setup_new_collection is not None:
            self.setup_new_collection(col)

        return col

    def open(self):
        """Open the collection, or create it if it doesn't exist."""
        if self.__col is None:
            if os.path.exists(self.path):
                self.__col = anki.storage.Collection(self.path)
            else:
                self.__col = self.__create_collection()

    def close(self):
        """Close the collection if opened."""
        if not self.opened():
            return

        self.__col.close()
        self.__col = None

    def opened(self):
        """Returns True if the collection is open, False otherwise."""
        return self.__col is not None

class CollectionManager(object):
    """Manages a set of CollectionWrapper objects."""

    collection_wrapper = CollectionWrapper

    def __init__(self):
        self.collections = {}

    def get_collection(self, path, setup_new_collection=None):
        """Gets a CollectionWrapper for the given path."""

        path = os.path.realpath(path)

        try:
            col = self.collections[path]
        except KeyError:
            col = self.collections[path] = self.collection_wrapper(path, setup_new_collection)

        return col

    def shutdown(self):
        """Close all CollectionWrappers managed by this object."""
        for path, col in self.collections.items():
            del self.collections[path]
            col.close()

