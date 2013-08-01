Anki Sync Server
================

A personal Anki sync server (so you can sync against your own server rather than AnkiWeb).

It also includes a RESTful API, so that you could implement your own AnkiWeb if wanted.

Installing
----------

Instructions for installing and running AnkiServer:

 1. First, you need to install "virtualenv".  If your system has easy_install, this is
    just a matter of:

      $ easy_install virtualenv

    If your system doesn't have easy_install, I recommend getting it!

 2. Next, you need to create a Python environment for running AnkiServer and install some of
    the dependencies we need there:

      $ virtualenv AnkiServer.env
      $ AnkiServer.env/bin/easy_install webob PasteDeploy PasteScript sqlalchemy simplejson

 3. Download and install libanki.  You can find the latest release of Anki here:

    http://code.google.com/p/anki/downloads/list

    Look for a *.tgz file with a Summary of "Anki Source".  At the time of this writing
    that is anki-2.0.11.tgz.

    Download this file and extract.

    Then either:

      a. Run the 'make install', or

      b. Copy the entire directory to /usr/share/anki

 4. Make the egg info files (so paster can see our app):

      $ AnkiServer.env/bin/python setup.py egg_info

 5. Copy the example.ini to production.ini and edit for your needs.

 6. Create authentication database:

      $ sqlite3 auth.db 'create table auth (user varchar primary key, hash varchar)'

 7. Create user:

      Enter username and password when prompted.

      $ read -p "Username: " USER && read -sp "Password: " PASS

      $ SALT=$(openssl rand -hex 8)

      $ HASH=$(echo -n $USER$PASS$SALT | sha256sum | sed 's/[ ]*-$//')$SALT

      $ sqlite3 test.db "INSERT INTO auth VALUES ('$USER', '$HASH')"

      $ mkdir -p collections/$USER

      $ unset USER PASS SALT HASH

 8. Then we can run AnkiServer like so:

      $ AnkiServer.env/bin/paster serve production.ini

