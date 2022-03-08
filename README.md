ankisyncd
=========

[![Documentation Status](https://readthedocs.org/projects/anki-sync-server/badge/?version=latest)](https://anki-sync-server.readthedocs.io/?badge=latest)
[![Gitter](https://badges.gitter.im/ankicommunity/community.svg)](https://gitter.im/ankicommunity/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

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
 - [Development](#development)
    - [Testing](#testing)
 - [ENVVAR configuration overrides](#envvar-configuration-overrides)
 - [Support for other database backends](#support-for-other-database-backends)
</details>

Installing
----------

1. Install the dependencies:

        $ pip install -r src/requirements.txt

2. Configuration: The config file can be found here: `https://github.com/ankicommunity/anki-sync-server/src/ankisyncd.conf`. Copying the config file from `src/ankisyncd.conf` to `src/ankisyncd/ankisyncd.conf` will allow you to configure the server. Subsequent commands refer to `/anki-sync-server/src/ankisyncd`.

3. Create user:

        $ ./ankisyncctl.py adduser <username>

4. Setup a proxy to unchunk the requests.

    Webob does not support the header "Transfer-Encoding: chunked" used by Anki
    and therefore ankisyncd sees chunked requests as empty. To solve this problem
    setup Nginx (or any other webserver of your choice) and configure it to
    "unchunk" the requests for ankisyncd.

    For example, if you use Nginx  on the same machine as ankisyncd, you first
    have to change the port in `ankisyncd.conf` to something other than `27701`.
    Then configure Nginx to listen on port `27701` and forward the unchunked
    requests to ankisyncd.

    An example configuration with ankisyncd running on the same machine as Nginx
    and listening on port `27702` may look like ([entire config template click me](https://github.com/ankicommunity/anki-sync-server/blob/develop/docs/nginx.conf)):

    ```nginx
    server {
    listen       27701;
    server_name   default;
    location / {
    proxy_http_version 1.0;
    proxy_pass         http://127.0.0.1:27702/;
    }
    }
     
    ```

5. Run ankisyncd:

```
$ python -m ankisyncd
```

---

Installing (Docker)
-------------------

Follow [these instructions](https://github.com/ankicommunity/anki-devops-services#about-this-docker-image).


Setting up Anki
---------------

### Install addon from ankiweb (support 2.1)

1.on add-on window,click `Get Add-ons` and fill in the textbox with the code  `358444159`

2.there,you get add-on `custom sync server redirector`,choose it.Then click `config`  below right

3.apply your server ip address 

if this step is taken,the following instructions regarding addon setting 2.1( including 2.1.28 and above) can be skipped.

### Anki 2.1.28 and above

Create a new directory in [the add-ons folder][addons21] (name it something
like ankisyncd), create a file named `__init__.py` containing the code below
and put it in the `ankisyncd` directory.

    import os
    
    addr = "http://127.0.0.1:27701/" # put your server address here
    os.environ["SYNC_ENDPOINT"] = addr + "sync/"
    os.environ["SYNC_ENDPOINT_MEDIA"] = addr + "msync/"

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

Use the same base url for both the `Sync url` and the `Media sync url`, but append `/msync` to
the `Media sync url`. Do **not** append `/sync` to the `Sync url`.

Even though the AnkiDroid interface will request an email address, this is not
required; it will simply be the username you configured with `ankisyncctl.py
adduser`.

Development
-----------

### Testing

0. Prerequites

This project uses [GNU Make](https://www.gnu.org/software/make/) to simplify the development commands. It also uses [Poetry](https://python-poetry.org/) to manage the Python dependencies. Ensure they are installed.

1. Create a config for your local environment.

```bash
$ cp config/.env.example config/.env.local
```

See [ENVVAR configuration overrides](#envvar-configuration-overrides) for more information.

2. Download Python dependencies.

```bash
$ make init
```

3. Run unit tests.

```bash
$ make tests
```

ENVVAR configuration overrides
------------------------------

Configuration values can be set via environment variables using `ANKISYNCD_` prepended
to the uppercase form of the configuration value. E.g. the environment variable,
`ANKISYNCD_AUTH_DB_PATH` will set the configuration value `auth_db_path`

Environment variables override the values set in the `ankisyncd.conf`.

* The environment variables can be found here: config/.env.example. 
* The file also includes other development variables, but the notable ones are the ones with the prefix ANKISYNCD_
* Environment variables will override the config files values (which is why I recommend you use them)
* This is what we use in the Docker images (see: https://github.com/ankicommunity/anki-devops-services/blob/develop/services/anki-sync-server/examples/docker-compose.yml).
* Copying the config file from config/.env.example to config/.env.local will allow you to configure the server when using the make commands
* You can also set it when running the server e.g. ANKISYNCD_PORT=5001 make run
* The above two options are useful for development. But if you're only going for usage, you can also set it globally by adding it to your ~/.bashrc file e.g. export ANKISYNCD_PORT=50001

Support for other database backends
-----------------------------------

sqlite3 is used by default for user data, authentication and session persistence.

`ankisyncd` supports loading classes defined via config that manage most
persistence requirements (the media DB and files are being worked on). All that is
required is to extend one of the existing manager classes and then reference those
classes in the config file. See ankisyncd.conf for example config.
