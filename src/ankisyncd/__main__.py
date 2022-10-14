import os
import sys

import ankisyncd
from ankisyncd.config import load_from_file
from ankisyncd.config import load_from_env
from ankisyncd import logging
from ankisyncd.sync_app import SyncApp
from ankisyncd.server import run_server

logger = logging.get_logger("ankisyncd")

if __package__ is None and not hasattr(sys, "frozen"):
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))


def main():
    logger.info(
        "ankisyncd {} ({})".format(ankisyncd._get_version(), ankisyncd._homepage)
    )

    config = load_from_file(sys.argv)
    load_from_env(config)

    ankiserver = SyncApp(config)
    run_server(ankiserver, config["host"], int(config["port"]))


if __name__ == "__main__":
    main()
