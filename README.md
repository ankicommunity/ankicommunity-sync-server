ankisyncd
=========

A personal Anki sync server (so you can sync against your own server rather than
AnkiWeb). This version has been simplified to remove some dependencies.

Installing
----------

### Manual installation

1. First, you need to install "virtualenv".  If your system has easy_install, this is
   just a matter of:

      $ easy_install virtualenv

   If your system doesn't have easy_install, I recommend getting it!

2. Next, you need to create a Python environment for running AnkiServer and install some of
   the dependencies we need there:

      $ virtualenv ankisyncd.env

      $ ankisyncd.env/bin/easy_install webob simplejson

3. Download and install libanki.  You can find the latest release of Anki here:

   http://code.google.com/p/anki/downloads/list

   Look for a *.tgz file with a Summary of "Anki Source".  At the time of this writing
   that is anki-2.0.11.tgz.

   Download this file and extract.

   Then either:

      a. Run the 'make install', or

      b. Copy the entire directory to /usr/share/anki

4. Copy the example.ini to production.ini and edit for your needs.

5. Create authentication database:

      $ sqlite3 auth.db 'CREATE TABLE auth (user VARCHAR PRIMARY KEY, hash VARCHAR)'

6. Create user:

      Enter username and password when prompted.

      $ read -p "Username: " USER && read -sp "Password: " PASS

      $ SALT=$(openssl rand -hex 8)

      $ HASH=$(echo -n "$USER$PASS$SALT" | sha256sum | sed 's/[ ]*-$//')$SALT

      $ sqlite3 auth.db "INSERT INTO auth VALUES ('$USER', '$HASH')"

      $ mkdir -p "collections/$USER"

      $ unset USER PASS SALT HASH

7. Then we can run AnkiServer like so:

      $ ankisyncd.env/bin/python src/sync_app.py
      
### Via PKGBUILD

There's PKGBUILD available for Arch Linux. To install, simply run:

   $ wget https://codeload.github.com/jdoe0/ankisyncd-pkgbuild/zip/master
      
   $ unzip master
      
   $ cd ankisyncd-pkgbuild-master
      
   $ makepkg -s
      
   $ sudo pacman -U *.xz
