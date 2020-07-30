import os
import sys

sys.path.insert(0, "/usr/share/anki")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "anki-bundled"))

_homepage = "https://github.com/tsudoko/anki-sync-server"
_unknown_version = "[unknown version]"


def _get_version():
    try:
        from ankisyncd._version import version

        return version
    except ImportError:
        pass

    import subprocess

    try:
        return (
            subprocess.run(
                ["git", "describe", "--always"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            .stdout.strip()
            .decode()
            or _unknown_version
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _unknown_version
