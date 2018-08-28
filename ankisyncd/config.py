import configparser
import logging
import os.path


def load(path=None):
    dirname = os.path.dirname
    realpath = os.path.realpath
    choices = [
        "/etc/ankisyncd/ankisyncd.conf",
        os.environ.get("XDG_CONFIG_DIR") and
            (os.path.join(os.environ['XDG_CONFIG_DIR'], "ankisyncd", "ankisyncd.conf")) or
            os.path.join(os.path.expanduser("~"), ".config", "ankisyncd", "ankisyncd.conf"),
        os.path.join(dirname(dirname(realpath(__file__))), "ankisyncd.conf"),
    ]
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
