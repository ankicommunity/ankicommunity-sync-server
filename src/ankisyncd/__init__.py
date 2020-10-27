import os
import sys

_homepage = "https://github.com/ankicommunity/anki-sync-server.git"
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
