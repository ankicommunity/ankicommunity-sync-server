import functools
import os
import sys

def __mediapatch():
    """
    Monkey-patch Anki's MediaManager to ignore the "server" attribute.

    It's needed because MediaManager's __init__(), connect() and close() are
    close to no-ops when self.col.server is True. If self.col.server is False,
    Syncer.usnLim() doesn't match entities that are supposed to be sent to the
    client, thus breaking server→client deck sync.
    """

    def noserver(f):
        @functools.wraps(f)
        def wrapped(self, *args, **kwargs):
            orig = self.col.server
            self.col.server = False
            ret = f(self, *args, **kwargs)
            self.col.server = orig
            return ret
        return wrapped

    from anki.media import MediaManager
    orig_init = MediaManager.__init__

    MediaManager.__init__ = functools.wraps(MediaManager.__init__)(lambda self, col, _: orig_init(self, col, False))
    MediaManager.connect = noserver(MediaManager.connect)
    MediaManager.close = noserver(MediaManager.close)

sys.path.insert(0, "/usr/share/anki")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "anki-bundled"))
__mediapatch()
