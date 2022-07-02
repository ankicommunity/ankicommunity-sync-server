#!/usr/bin/env python3

import sys
import getpass

from ankisyncd import config
from ankisyncd.users import get_user_manager


config = config.load()

def usage():
    print("usage: {} <command> [<args>]".format(sys.argv[0]))
    print()
    print("Commands:")
    print("  adduser <username> - add a new user")
    print("  deluser <username> - delete a user")
    print("  lsuser             - list users")
    print("  passwd <username>  - change password of a user")

def adduser(username):
    password = getpass.getpass("Enter password for {}: ".format(username))

    user_manager = get_user_manager(config)
    user_manager.add_user(username, password)

def deluser(username):
    user_manager = get_user_manager(config)
    try:
        user_manager.del_user(username)
    except ValueError as error:
        print("Could not delete user {}: {}".format(username, error), file=sys.stderr)

def lsuser():
    user_manager = get_user_manager(config)
    try:
        users = user_manager.user_list()
        for username in users:
            print(username)
    except ValueError as error:
        print("Could not list users: {}".format(error), file=sys.stderr)

def passwd(username):
    user_manager = get_user_manager(config)

    if username not in user_manager.user_list():
        print("User {} doesn't exist".format(username))
        return

    password = getpass.getpass("Enter password for {}: ".format(username))
    try:
        user_manager.set_password_for_user(username, password)
    except ValueError as error:
        print("Could not set password for user {}: {}".format(username, error), file=sys.stderr)

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
