# -*- coding: utf-8 -*-

from ankisyncd import logging
from ankisyncd.full_sync.manager import FullSyncManager

logger = logging.get_logger(__name__)
logger.setLevel(1)


def get_full_sync_manager(config):
    if (
        "full_sync_manager" in config and config["full_sync_manager"]
    ):  # load from config
        import importlib
        import inspect

        module_name, class_name = config["full_sync_manager"].rsplit(".", 1)
        module = importlib.import_module(module_name.strip())
        class_ = getattr(module, class_name.strip())

        if not FullSyncManager in inspect.getmro(class_):
            raise TypeError(
                """"full_sync_manager" found in the conf file but it doesn''t
                            inherit from FullSyncManager"""
            )
        return class_(config)
    else:
        return FullSyncManager()
