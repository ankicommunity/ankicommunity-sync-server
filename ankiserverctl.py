#!/usr/bin/env python

import os
import sys
import signal
import subprocess
import binascii
import getpass
import hashlib
import sqlite3

SERVERCONFIG = "production.ini"
AUTHDBPATH = "auth.db"
PIDPATH = "/tmp/ankiserver.pid"
COLLECTIONPATH = "collections/"

def usage():
    print "usage: "+sys.argv[0]+" <command> [<args>]"
    print
    print "Commands:"
    print "  start [configfile] - start the server"
    print "  debug [configfile] - start the server in debug mode"
    print "  stop               - stop the server"
    print "  adduser <username> - add a new user"
    print "  deluser <username> - delete a user"
    print "  lsuser             - list users"
    print "  passwd <username>  - change password of a user"

def startsrv(configpath, debug):
    if not configpath:
        configpath = SERVERCONFIG

    # We change to the directory containing the config file
    # so that all the paths will be relative to it.
    configdir = os.path.dirname(configpath)
    if configdir != '':
        os.chdir(configdir)
    configpath = os.path.basename(configpath)

    if debug:
        # Start it in the foreground and wait for it to complete.
        subprocess.call( ["paster", "serve", configpath], shell=False)
        return

    devnull = open(os.devnull, "w")
    pid = subprocess.Popen( ["paster", "serve", configpath],
                            stdout=devnull,
                            stderr=devnull).pid

    with open(PIDPATH, "w") as pidfile:
        pidfile.write(str(pid))

def stopsrv():
    if os.path.isfile(PIDPATH):
        try:
            with open(PIDPATH) as pidfile:
                pid = int(pidfile.read())

                os.kill(pid, signal.SIGKILL)
                os.remove(PIDPATH)
        except Exception, error:
            print >>sys.stderr, sys.argv[0]+": Failed to stop server: "+error.message
    else:
        print >>sys.stderr, sys.argv[0]+": The server is not running"

def adduser(username):
    if username:
        print "Enter password for "+username+": "

        password = getpass.getpass()
        salt = binascii.b2a_hex(os.urandom(8))
        hash = hashlib.sha256(username+password+salt).hexdigest()+salt

        conn = sqlite3.connect(AUTHDBPATH)
        cursor = conn.cursor()

        cursor.execute( "CREATE TABLE IF NOT EXISTS auth "
                        "(user VARCHAR PRIMARY KEY, hash VARCHAR)")

        cursor.execute("INSERT INTO auth VALUES (?, ?)", (username, hash))

        if not os.path.isdir(COLLECTIONPATH+username):
            os.makedirs(COLLECTIONPATH+username)

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
        print "Enter password for "+username+": "

        password = getpass.getpass()
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
    exitcode = 0

    if argc < 2:
        usage()
        exitcode = 1
    else:
        if argc < 3:
            sys.argv.append(None)

        if sys.argv[1] == "start":
            startsrv(sys.argv[2], False)
        elif sys.argv[1] == "debug":
            startsrv(sys.argv[2], True)
        elif sys.argv[1] == "stop":
            stopsrv()
        elif sys.argv[1] == "adduser":
            adduser(sys.argv[2])
        elif sys.argv[1] == "deluser":
            deluser(sys.argv[2])
        elif sys.argv[1] == "lsuser":
            lsuser()
        elif sys.argv[1] == "passwd":
            passwd(sys.argv[2])
        else:
            usage()
            exitcode = 1

    sys.exit(exitcode)

if __name__ == "__main__":
    main()
