ankisyncd
=========

[Anki][] is a powerful open source flashcard application, which helps you
quickly and easily memorize facts over the long term utilizing a spaced
repetition algorithm. Anki's main form is a desktop application (for Windows,
Linux and macOS) which can sync to a web version (AnkiWeb) and mobile
versions for Android and iOS.

This is a personal Anki server, which you can sync against instead of
AnkiWeb. It was originally developed to support the flashcard functionality
on Bibliobird, a web application for language learning.

This version is a fork of [jdoe0/ankisyncd](https://github.com/jdoe0/ankisyncd).
It supports Python 3 and Anki 2.1.

Installing
----------

0. Install Anki. The server currently works well with 2.1.1. If for some reason
   you can't get this version easily on your system, you can use `anki-bundled`
   from this repo:

        $ git submodule update --init
        $ cd anki
        $ pip install -r requirements.txt

1. Install the dependencies:

        $ pip install webob

2. Modify ankisyncd.conf according to your needs

3. Create user:

        $ ./ankisyncctl.py adduser <username>

4. Run ankisyncd:

        $ python -m ankisyncd ankisyncd.conf

Setting up Anki
---------------

### Anki 2.1

Create a new directory in `~/Anki/addons21` (name it something like ankisyncd),
create a file named `__init__.py` containing the code below and put it in
`~/Anki/addons21/ankisyncd`.

    import anki.sync

    anki.sync.SYNC_BASE = 'http://127.0.0.1:27701/%s'

### Anki 2.0

To make Anki use ankisyncd as its sync server, create a file (name it something
like ankisyncd.py) containing the code below and put it in `~/Anki/addons`.

    import anki.sync

    anki.sync.SYNC_BASE = 'http://127.0.0.1:27701/'
    anki.sync.SYNC_MEDIA_BASE = 'http://127.0.0.1:27701/msync/'

Replace 127.0.0.1 with the IP address or the domain name of your server if
ankisyncd is not running on the same machine as Anki.

[Anki]: https://apps.ankiweb.net/
[dsnopek's Anki Sync Server]: https://github.com/dsnopek/anki-sync-server
