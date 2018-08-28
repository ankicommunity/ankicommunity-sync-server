import configparser
import logging
import os
from os.path import dirname, realpath

paths = [
    "/etc/ankisyncd/ankisyncd.conf",
    os.environ.get("XDG_CONFIG_HOME") and
        (os.path.join(os.environ['XDG_CONFIG_HOME'], "ankisyncd", "ankisyncd.conf")) or
        os.path.join(os.path.expanduser("~"), ".config", "ankisyncd", "ankisyncd.conf"),
    os.path.join(dirname(dirname(realpath(__file__))), "ankisyncd.conf"),
]


def load(path=None):
    choices = paths
    parser = configparser.ConfigParser()
    if path:
        choices = [path]
    for path in choices:
        logging.debug("config.location: trying", path)
        try:
            parser.read(path)
            conf = parser['sync_app']
            logging.info("Loaded config from {}".format(path))
            return conf
        except KeyError:
            pass
    raise Exception("No config found, looked for {}".format(", ".join(choices)))
