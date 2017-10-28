#!/usr/bin/env python

import os
import sys
import binascii
import getpass
import hashlib
import sqlite3

DATAPREFIX = os.path.join(os.path.expanduser("~"), ".local", "share")
DATADIR = os.path.join(DATAPREFIX, "ankisyncd")
AUTHDBPATH = os.path.join(DATADIR, "auth.db")
COLLECTIONPATH = os.path.join(DATADIR, "collections")

def usage():
    print "usage: "+sys.argv[0]+" <command> [<args>]"
    print
    print "Commands:"
    print "  adduser <username> - add a new user"
    print "  deluser <username> - delete a user"
    print "  lsuser             - list users"
    print "  passwd <username>  - change password of a user"

def adduser(username):
    if username:
        password = getpass.getpass("Enter password for "+username+": ")
        salt = binascii.b2a_hex(os.urandom(8))
        hash = hashlib.sha256(username+password+salt).hexdigest()+salt

        conn = sqlite3.connect(AUTHDBPATH)
        cursor = conn.cursor()

        cursor.execute( "CREATE TABLE IF NOT EXISTS auth "
                        "(user VARCHAR PRIMARY KEY, hash VARCHAR)")

        cursor.execute("INSERT INTO auth VALUES (?, ?)", (username, hash))

        colpath = os.path.join(COLLECTIONPATH, username)
        if not os.path.isdir(colpath):
            os.makedirs(colpath)

        conn.commit()
        conn.close()
    else:
        usage()

def deluser(username):
    if username and os.path.isfile(AUTHDBPATH):
            conn = sqlite3.connect(AUTHDBPATH)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM auth WHERE user=?", (username,))

            conn.commit()
            conn.close()
    elif not username:
        usage()
    else:
        print >>sys.stderr, sys.argv[0]+": Database file does not exist"

def lsuser():
    conn = sqlite3.connect(AUTHDBPATH)
    cursor = conn.cursor()

    cursor.execute("SELECT user FROM auth")

    row = cursor.fetchone()

    while row is not None:
        print row[0]

        row = cursor.fetchone()

    conn.close()

def passwd(username):
    if os.path.isfile(AUTHDBPATH):
        password = getpass.getpass("Enter password for "+username+": ")
        salt = binascii.b2a_hex(os.urandom(8))
        hash = hashlib.sha256(username+password+salt).hexdigest()+salt

        conn = sqlite3.connect(AUTHDBPATH)
        cursor = conn.cursor()

        cursor.execute("UPDATE auth SET hash=? WHERE user=?", (hash, username))

        conn.commit()
        conn.close()
    else:
        print >>sys.stderr, sys.argv[0]+": Database file does not exist"

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
