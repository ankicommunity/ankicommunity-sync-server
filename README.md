<div align="center">

# ankicommunity-sync-server


[![Python version](https://img.shields.io/pypi/pyversions/anki-sync-server)](https://github.com/ankicommunity/anki-sync-server/blob/develop/pyproject.toml)
[![License](https://img.shields.io/github/license/ankicommunity/anki-sync-server)](https://github.com/ankicommunity/anki-sync-server/blob/develop/COPYING)
[![Last commit](https://img.shields.io/github/last-commit/ankicommunity/anki-sync-server)](https://github.com/ankicommunity/anki-sync-server/commits/develop)
<br />
[![Github status](https://img.shields.io/github/checks-status/ankicommunity/anki-sync-server/develop?label=github%20status)](https://github.com/ankicommunity/anki-sync-server/actions)
[![Github version](https://img.shields.io/github/v/tag/ankicommunity/anki-sync-server?label=github%20version)](https://github.com/ankicommunity/anki-sync-server/releases)
[![Github contributors](https://img.shields.io/github/contributors/ankicommunity/anki-sync-server?label=github%20contributors)](https://github.com/ankicommunity/anki-sync-server/graphs/contributors)
[![Github sponsors](https://img.shields.io/github/sponsors/ankicommunity?label=github%20sponsors)](https://github.com/sponsors/ankicommunity)
<br />
[![PyPI version](https://img.shields.io/pypi/v/anki-sync-server?label=pypi%20version)](https://pypi.org/project/anki-sync-server)
[![PyPI downloads](https://img.shields.io/pypi/dm/anki-sync-server?label=pypi%20downloads)](https://pypi.org/project/anki-sync-server)
<br />
[![DockerHub version](https://img.shields.io/docker/v/ankicommunity/anki-sync-server?label=dockerhub%20version&sort=date)](https://hub.docker.com/repository/docker/ankicommunity/anki-sync-server)
[![DockerHub pulls](https://img.shields.io/docker/pulls/ankicommunity/anki-sync-server)](https://hub.docker.com/repository/docker/ankicommunity/anki-sync-server)
[![DockerHub stars](https://img.shields.io/docker/stars/ankicommunity/anki-sync-server)](https://hub.docker.com/repository/docker/ankicommunity/anki-sync-server)
<br />
[![Readthedocs status](https://img.shields.io/readthedocs/anki-sync-server?label=readthedocs%20status)](https://anki-sync-server.readthedocs.io/?badge=latest)
[![Gitter](https://badges.gitter.im/ankicommunity/community.svg)](https://gitter.im/ankicommunity/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

</div>

------------

Known Issues
------------

**⚠️ This project is incompatible with Anki Desktop >=2.1.57 ⚠️**

We're working hard to update to the new syncing protocol.

In the mean time, we recommend you check out the offical sync server here:
- [Documentation](https://docs.ankiweb.net/sync-server.html)
- [Repository](https://github.com/ankitects/anki)
- [WIP Docker Image](https://github.com/ankitects/anki/pull/2798#issuecomment-1812839066)

Or reach out to see how you can help support our development [here](https://github.com/ankicommunity/anki-sync-server/issues/158).

Thank you for your understanding. 

------------


[Anki][] is a powerful open source flashcard application, which helps you
quickly and easily memorize facts over the long term utilizing a spaced
repetition algorithm. Anki's main form is a desktop application (for Windows,
Linux and macOS) which can sync to a web version (AnkiWeb) and mobile
versions for Android and iOS.

This is a personal Anki server, which you can sync against instead of
AnkiWeb. 

[Anki]: https://apps.ankiweb.net/


<details open><summary>Contents</summary>

 - [Installing](#installing)
 - [Installing (Docker)](#installing-docker)
 - [Setting up Anki](#setting-up-anki)
    - [Anki 2.1](#anki-21)
    - [Anki 2.0](#anki-20)
    - [AnkiDroid](#ankidroid)
 - [Development](#development)
    - [Testing](#testing)
 - [Configuration](#configuration)
    - [Environment Variables](#environment-variables-preferred)
    - [Config File](#config-file-ankisyncdconf)
 - [Support for other database backends](#support-for-other-database-backends)
</details>


Installing
----------

1. Install the dependencies:

        $ pip install -r src/requirements.txt
        $ pip install -e src

2. Copy the default config file ([ankisyncd.conf](src/ankisyncd.conf)) to configure the server using the command below. Environment variables can be used instead, see: [Configuration](#configuration).

        $ cp src/ankisyncd.conf src/ankisyncd/.

3. Create user:

        $ python -m ankisyncd_cli adduser <username>

4. Ankisyncd can serve the requests directly. However, if you want better
   security and SSL encryption, a proxy can be set up.

   For example, you can use Nginx. First, obtain the SSL certificate from
   [Let's Encrypt](https://letsencrypt.org) via
   [certbot](https://certbot.eff.org/). Nginx will accept the requests at
   standard HTTPS port 443 and forward the traffic to ankisyncd which runs by
   default on port `27701` ([configuration](#configuration)).

   An example of configuration for domain `example.com`:

    ```nginx
    server {
        listen        443 ssl;
        server_name   example.com;

        # Configuration managed by Certbot
        ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
        include /etc/letsencrypt/options-ssl-nginx.conf;

        location / {
            proxy_http_version   1.0;
            proxy_pass           http://127.0.0.1:27702/;
            client_max_body_size 222M;
        }
    }
    ```

    Adding the line `client_max_body_size 222M;` to Nginx prevents bigger
    collections from not being able to sync due to size limitations.

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

[addons21]: https://addon-docs.ankiweb.net/addon-folders.html

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

See [Configuration](#configuration) for more information.

2. Download Python dependencies.

```bash
$ make init
```

3. Run unit tests.

```bash
$ make tests
```

## Configuration

### Environment Variables (preferred)

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

### Config File: ankisyncd.conf

A config file can be used to configuring the server. It can be found here: [src/ankisyncd.conf](src/ankisyncd.conf).


Support for other database backends
-----------------------------------

sqlite3 is used by default for user data, authentication and session persistence.

`ankisyncd` supports loading classes defined via config that manage most
persistence requirements (the media DB and files are being worked on). All that is
required is to extend one of the existing manager classes and then reference those
classes in the config file. See ankisyncd.conf for example config.

## Acknowledgment

- This server was originally developed by [David Snopek](https://github.com/dsnopek)
to support the flashcard functionality on Bibliobird, a web application for
language learning.
- It was then forked by `jdoe0` to add supports Python 3 and Anki 2.1.
- It was then forked by [tsudoko](https://github.com/tsudoko) which was the base for this repo.
