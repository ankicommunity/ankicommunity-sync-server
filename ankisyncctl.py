#!/usr/bin/env python
import os
import sys
import getpass

import ankisyncd.config
from ankisyncd.users import SqliteUserManager

config = ankisyncd.config.load()
AUTHDBPATH = config['auth_db_path']
COLLECTIONPATH = config['data_root']

def usage():
    print("usage: "+sys.argv[0]+" <command> [<args>]")
    print()
    print("Commands:")
    print("  adduser <username> - add a new user")
    print("  deluser <username> - delete a user")
    print("  lsuser             - list users")
    print("  passwd <username>  - change password of a user")

def adduser(username):
    if username:
        password = getpass.getpass("Enter password for {}: ".format(username))

        user_manager = SqliteUserManager(AUTHDBPATH, COLLECTIONPATH)
        user_manager.add_user(username, password)
    else:
        usage()

def deluser(username):
    if username and os.path.isfile(AUTHDBPATH):
        user_manager = SqliteUserManager(AUTHDBPATH, COLLECTIONPATH)

        try:
            user_manager.del_user(username)
        except ValueError as error:
            print("Could not delete user {}: {}"
                  .format(username, error.message), file=sys.stderr)
    elif not username:
        usage()
    else:
        print("{}: Database file does not exist".format(sys.argv[0]),
              file=sys.stderr)

def lsuser():
    user_manager = SqliteUserManager(AUTHDBPATH, COLLECTIONPATH)
    try:
        users = user_manager.user_list()
        for username in users:
            print(username)
    except ValueError as error:
        print("Could not list users: {}".format(AUTHDBPATH, error.message),
              file=sys.stderr)

def passwd(username):
    if os.path.isfile(AUTHDBPATH):
        password = getpass.getpass("Enter password for {}: ".format(username))

        user_manager = SqliteUserManager(AUTHDBPATH, COLLECTIONPATH)
        try:
            user_manager.set_password_for_user(username, password)
        except ValueError as error:
            print("Could not set password for user {}: {}"
                  .format(username, error.message), file=sys.stderr)
    else:
        print("{}: Database file does not exist".format(sys.argv[0]),
              file=sys.stderr)

def main():
    argc = len(sys.argv)

    cmds = {
        "adduser": adduser,
        "deluser": deluser,
        "lsuser": lsuser,
        "passwd": passwd,
    }

    if argc < 2:
        usage()
        exit(1)

    c = sys.argv[1]
    try:
        if argc > 2:
            for arg in sys.argv[2:]:
                cmds[c](arg)
        else:
            cmds[c]()
    except KeyError:
        usage()
        exit(1)

if __name__ == "__main__":
    main()
