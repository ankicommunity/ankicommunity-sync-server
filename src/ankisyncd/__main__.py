import os
import sys
import logging


import ankisyncd
import ankisyncd.config
from ankisyncd.sync_app import SyncApp
from ankisyncd.server import run_server

logger = logging.getLogger("ankisyncd")

if __package__ is None and not hasattr(sys, "frozen"):
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))


def main():
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s]:%(levelname)s:%(name)s:%(message)s"
    )
    logger.info(
        "ankisyncd {} ({})".format(ankisyncd._get_version(), ankisyncd._homepage)
    )

    if len(sys.argv) > 1:
        # backwards compat
        config = ankisyncd.config.load(sys.argv[1])
    else:
        config = ankisyncd.config.load()

    ankiserver = SyncApp(config)
    run_server(ankiserver, config["host"], int(config["port"]))


if __name__ == "__main__":
    main()
