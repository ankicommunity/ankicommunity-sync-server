# -*- coding: utf-8 -*-

import importlib
import inspect
from ankisyncd import logging
from ankisyncd.sessions.simple_manager import SimpleSessionManager
from ankisyncd.sessions.sqlite_manager import SqliteSessionManager

logger = logging.get_logger(__name__)


def get_session_manager(config):
    if "session_db_path" in config and config["session_db_path"]:
        logger.info(
            "Found session_db_path in config, using SqliteSessionManager for auth"
        )
        return SqliteSessionManager(config["session_db_path"])
    elif "session_manager" in config and config["session_manager"]:  # load from config
        logger.info(
            "Found session_manager in config, using {} for persisting sessions".format(
                config["session_manager"]
            )
        )

        module_name, class_name = config["session_manager"].rsplit(".", 1)
        module = importlib.import_module(module_name.strip())
        class_ = getattr(module, class_name.strip())

        if not SimpleSessionManager in inspect.getmro(class_):
            raise TypeError(
                """"session_manager" found in the conf file but it doesn''t
                            inherit from SimpleSessionManager"""
            )
        return class_(config)
    else:
        logger.warning(
            "Neither session_db_path nor session_manager set, "
            "ankisyncd will lose sessions on application restart"
        )
        return SimpleSessionManager()
