ankisyncd
=========

[Anki][] is a powerful open source flashcard application, which helps you
quickly and easily memorize facts over the long term utilizing a spaced
repetition algorithm. Anki's main form is a desktop application (for Windows,
Linux and macOS) which can sync to a web version (AnkiWeb) and mobile
versions for Android and iOS.

This is a personal Anki server, which you can sync against instead of
AnkiWeb. It was originally developed by [David Snopek](https://github.com/dsnopek)
to support the flashcard functionality on Bibliobird, a web application for
language learning.

This version is a fork of [jdoe0/ankisyncd](https://github.com/jdoe0/ankisyncd).
It supports Python 3 and Anki 2.1.

[Anki]: https://apps.ankiweb.net/
[dsnopek's Anki Sync Server]: https://github.com/dsnopek/anki-sync-server

<details open><summary>Contents</summary>

 - [Installing](#installing)
 - [Installing (Docker)](#installing-docker)
 - [Setting up Anki](#setting-up-anki)
   - [Anki 2.1](#anki-21)
   - [Anki 2.0](#anki-20)
   - [AnkiDroid](#ankidroid)
 - [Running `ankisyncd` without `pyaudio`](#running-ankisyncd-without-pyaudio)
   - [Anki ≥2.1.9](#anki-219)
   - [Older versions](#older-versions)
 - [ENVVAR configuration overrides](#envvar-configuration-overrides)
 - [Support for other database backends](#support-for-other-database-backends)
</details>

Installing
----------

0. Install Anki. The currently supported version range is 2.1.1〜2.1.11, with the
   exception of 2.1.9<sup id="readme-fn-01b">[1](#readme-fn-01)</sup>. (Keep in
   mind this range only applies to the Anki used by the server, clients can be
   as old as 2.0.27 and still work.) Running the server with other versions might
   work as long as they're not 2.0.x, but things might break, so do it at your
   own risk. If for some reason you can't get the supported Anki version easily
   on your system, you can use `anki-bundled` from this repo:

        $ git submodule update --init
        $ cd anki-bundled
        $ pip install -r requirements.txt

   Keep in mind `pyaudio`, a dependency of Anki, requires development headers for
   Python 3 and PortAudio to be present before running `pip`. If you can't or
   don't want to install these, you can try [patching Anki](#running-ankisyncd-without-pyaudio).

1. Install the dependencies:

        $ pip install webob

2. Modify ankisyncd.conf according to your needs

3. Create user:

        $ ./ankisyncctl.py adduser <username>

4. Run ankisyncd:

        $ python -m ankisyncd

---

<span id="readme-fn-01"></span>
1. 2.1.9 is not supported due to [commit `95ccbfdd3679`][] introducing the
   dependency on the `aqt` module, which depends on PyQt5. The server should
   still work fine if you have PyQt5 installed. This has been fixed in
   [commit `a389b8b4a0e2`][], which is a part of the 2.1.10 release.
[↑](#readme-fn-01b)

[commit `95ccbfdd3679`]: https://github.com/dae/anki/commit/95ccbfdd3679dd46f22847c539c7fddb8fa904ea
[commit `a389b8b4a0e2`]: https://github.com/dae/anki/commit/a389b8b4a0e209023c4533a7ee335096a704079c

Installing (Docker)
-------------------

Follow [these instructions](https://github.com/kuklinistvan/docker-anki-sync-server#usage).

Setting up Anki
---------------

### Anki 2.1

Create a new directory in [the add-ons folder][addons21] (name it something
like ankisyncd), create a file named `__init__.py` containing the code below
and put it in the `ankisyncd` directory.

    import anki.sync, anki.hooks, aqt

    addr = "http://127.0.0.1:27701/" # put your server address here
    anki.sync.SYNC_BASE = "%s" + addr
    def resetHostNum():
        aqt.mw.pm.profile['hostNum'] = None
    anki.hooks.addHook("profileLoaded", resetHostNum)

### Anki 2.0

Create a file (name it something like ankisyncd.py) containing the code below
and put it in `~/Anki/addons`.

    import anki.sync

    addr = "http://127.0.0.1:27701/" # put your server address here
    anki.sync.SYNC_BASE = addr
    anki.sync.SYNC_MEDIA_BASE = addr + "msync/"

[addons21]: https://addon-docs.ankiweb.net/#/getting-started?id=add-on-folders

### AnkiDroid

Advanced → Custom sync server

Unless you have set up a reverse proxy to handle encrypted connections, use
`http` as the protocol. The port will be either the default, 27701, or
whatever you have specified in `ankisyncd.conf` (or, if using a reverse proxy,
whatever port you configured to accept the front-end connection).

**Do not use trailing slashes.**

Even though the AnkiDroid interface will request an email address, this is not
required; it will simply be the username you configured with `ankisyncctl.py
adduser`.

Running `ankisyncd` without `pyaudio`
-------------------------------------

`ankisyncd` doesn't use the audio recording feature of Anki, so if you don't
want to install PortAudio, you can edit some files in the `anki-bundled`
directory to exclude `pyaudio`:

### Anki ≥2.1.9

Just remove "pyaudio" from requirements.txt and you're done. This change has
been introduced in [commit `ca710ab3f1c1`][].

[commit `ca710ab3f1c1`]: https://github.com/dae/anki/commit/ca710ab3f1c1174469a3b48f1257c0fc0ce624bf

### Older versions

First go to `anki-bundled`, then follow one of the instructions below. They all
do the same thing, you can pick whichever one you're most comfortable with.

Manual version: remove every line past "# Packaged commands" in anki/sound.py,
remove every line starting with "pyaudio" in requirements.txt

`ed` version:

    $ echo '/# Packaged commands/,$d;w' | tr ';' '\n' | ed anki/sound.py
    $ echo '/^pyaudio/d;w' | tr ';' '\n' | ed requirements.txt

`sed -i` version:

    $ sed -i '/# Packaged commands/,$d' anki/sound.py
    $ sed -i '/^pyaudio/d' requirements.txt

ENVVAR configuration overrides
------------------------------

Configuration values can be set via environment variables using `ANKISYNCD_` prepended
to the uppercase form of the configuration value. E.g. the environment variable,
`ANKISYNCD_AUTH_DB_PATH` will set the configuration value `auth_db_path`

Environment variables override the values set in the `ankisyncd.conf`.

Support for other database backends
-----------------------------------

sqlite3 is used by default for user data, authentication and session persistence.

`ankisyncd` supports loading classes defined via config that manage most
persistence requirements (the media DB and files are being worked on). All that is
required is to extend one of the existing manager classes and then reference those
classes in the config file. See ankisyncd.conf for example config.
