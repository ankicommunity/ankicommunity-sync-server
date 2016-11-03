ankisyncd
=========

A personal Anki sync server (so you can sync against your own server rather than
AnkiWeb). This version has been modified from dsnopek's Anki Sync Server to
remove the REST API, which makes it possible to drop some dependencies.

Installing
----------

### Manual installation

1. First, you need to install "virtualenv".  If your system has easy_install,
this is just a matter of:

        $ easy_install virtualenv

    If your system doesn't have easy_install, I recommend getting it!

2. Next, you need to create a Python environment for running ankisyncd and
install some of the dependencies we need there:

        $ virtualenv ankisyncd.env
        $ ankisyncd.env/bin/easy_install webob simplejson eventlet

3. Patch the bundled libanki:

	$ ./patch_libanki.sh

4. Copy the example.ini to production.ini and edit for your needs. Warning: If
   you disable SSL, login credentials will be transported in plain text!

5. Create authentication database:

        $ sqlite3 auth.db 'CREATE TABLE auth (user VARCHAR PRIMARY KEY, hash VARCHAR)'

6. Create user:

        $ ./ankisyncctl.py adduser <username>

7. Then we can run ankisyncd like so:

        $ ./ankisyncctl.py start

    To stop the server, run:

        $ ./ankisyncctl.py stop

Setting up Anki
---------------

To make Anki use ankisyncd as its sync server, create a file (name it something
like ankisyncd.py) containing the code below and put it in ~/Anki/addons.

    import anki.sync
    import httplib2

    anki.sync.SYNC_BASE = 'http://127.0.0.1:27701/'
    anki.sync.SYNC_MEDIA_BASE = 'http://127.0.0.1:27701/msync/'
    anki.sync.httpCon = lambda: httplib2.Http()

Replace 127.0.0.1 with the IP address or the domain name of your server if
ankisyncd is not running on the same machine as Anki.
