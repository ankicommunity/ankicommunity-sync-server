from ankisyncd import logging
from ankisyncd.collection.wrapper import CollectionWrapper
from ankisyncd.collection.manager import CollectionManager

logger = logging.get_logger(__name__)


def get_collection_wrapper(config, path, setup_new_collection=None):
    if "collection_wrapper" in config and config["collection_wrapper"]:
        logger.info(
            "Found collection_wrapper in config, using {} for "
            "user data persistence".format(config["collection_wrapper"])
        )
        import importlib
        import inspect

        module_name, class_name = config["collection_wrapper"].rsplit(".", 1)
        module = importlib.import_module(module_name.strip())
        class_ = getattr(module, class_name.strip())

        if not CollectionWrapper in inspect.getmro(class_):
            raise TypeError(
                """"collection_wrapper" found in the conf file but it doesn''t
                            inherit from CollectionWrapper"""
            )
        return class_(config, path, setup_new_collection)
    else:
        return CollectionWrapper(config, path, setup_new_collection)
