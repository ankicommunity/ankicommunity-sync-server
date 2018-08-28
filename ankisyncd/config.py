import configparser
import logging
import os.path


def location():
    dirname = os.path.dirname
    realpath = os.path.realpath
    choices = [
        "/etc/ankisyncd/ankisyncd.conf",
        os.environ.get("XDG_CONFIG_DIR") and
            (os.path.join(os.environ['XDG_CONFIG_DIR'], "ankisyncd", "ankisyncd.conf")) or
            os.path.join(os.path.expanduser("~"), ".config", "ankisyncd", "ankisyncd.conf"),
        os.path.join(dirname(dirname(realpath(__file__))), "ankisyncd.conf"),
    ]
    for path in choices:
        logging.debug("config.location: trying", path)
        if os.path.isfile(path):
            logging.debug("config.location: choosing", path)
            return path

    logging.error("No config found, looked in", ", ".join(choices))


def load(path=location()):
    logging.info("Loading config from {}".format(path))
    parser = configparser.ConfigParser()
    parser.read(path)
    return parser['sync_app']
