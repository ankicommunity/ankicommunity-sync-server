import os

from ankisyncd.collection.wrapper import CollectionWrapper


class CollectionManager:
    """Manages a set of CollectionWrapper objects."""

    collection_wrapper = CollectionWrapper

    def __init__(self, config):
        self.collections = {}
        self.config = config

    def get_collection(self, path, setup_new_collection=None):
        """Gets a CollectionWrapper for the given path."""

        path = os.path.realpath(path)

        try:
            col = self.collections[path]
        except KeyError:
            col = self.collections[path] = self.collection_wrapper(
                self.config, path, setup_new_collection
            )

        return col

    def shutdown(self):
        """Close all CollectionWrappers managed by this object."""
        for path, col in list(self.collections.items()):
            del self.collections[path]
            col.close()
