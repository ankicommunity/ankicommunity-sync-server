# -*- coding: utf-8 -*-

import importlib
import inspect

from ankisyncd import logging
from ankisyncd.users.simple_manager import SimpleUserManager
from ankisyncd.users.sqlite_manager import SqliteUserManager

logger = logging.get_logger(__name__)


def get_user_manager(config):
    if "auth_db_path" in config and config["auth_db_path"]:
        logger.info("Found auth_db_path in config, using SqliteUserManager for auth")
        return SqliteUserManager(config["auth_db_path"], config["data_root"])
    elif "user_manager" in config and config["user_manager"]:  # load from config
        logger.info(
            "Found user_manager in config, using {} for auth".format(
                config["user_manager"]
            )
        )

        module_name, class_name = config["user_manager"].rsplit(".", 1)
        module = importlib.import_module(module_name.strip())
        class_ = getattr(module, class_name.strip())

        if not SimpleUserManager in inspect.getmro(class_):
            raise TypeError(
                """"user_manager" found in the conf file but it doesn''t
                            inherit from SimpleUserManager"""
            )
        return class_(config)
    else:
        logger.warning(
            "neither auth_db_path nor user_manager set, ankisyncd will accept any password"
        )
        return SimpleUserManager()
