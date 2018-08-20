import sys

if __package__ is None and not hasattr(sys, "frozen"):
    import os.path
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))

import ankisyncd.sync_app

if __name__ == "__main__":
    ankisyncd.sync_app.main()
