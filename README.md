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

This version has been modified from [dsnopek's Anki Sync Server][] to remove
the REST API, which makes it possible to drop some dependencies.

Installing
----------

1. Install the dependencies:

        $ pip install webob

2. Modify ankisyncd.conf according to your needs

3. Create user:

        $ ./ankisyncctl.py adduser <username>

4. Run ankisyncd:

        $ python ./ankisyncd/sync_app.py ankisyncd.conf

Setting up Anki
---------------

To make Anki use ankisyncd as its sync server, create a file (name it something
like ankisyncd.py) containing the code below and put it in ~/Anki/addons.

    import anki.sync

    anki.sync.SYNC_BASE = 'http://127.0.0.1:27701/'
    anki.sync.SYNC_MEDIA_BASE = 'http://127.0.0.1:27701/msync/'

Replace 127.0.0.1 with the IP address or the domain name of your server if
ankisyncd is not running on the same machine as Anki.

[Anki]: https://apps.ankiweb.net/
[dsnopek's Anki Sync Server]: https://github.com/dsnopek/anki-sync-server
