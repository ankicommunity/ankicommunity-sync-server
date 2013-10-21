#! /usr/bin/env bash

SERVERCONFIG="production.ini"
AUTHDBPATH="auth.db"
PIDPATH="/tmp/ankiserver.pid"

usage()
{
	echo "usage: $0 <command> [<args>]"
	echo
	echo "Commands:"
	echo "	start [configfile]	- start the server"
	echo "	stop			- stop the server"
	echo "	adduser <username>	- add a new user"
	echo "	deluser <username>	- delete a user"
	echo "	passwd <username>	- change password of a user"

	exit 1
}

startsrv()
{
	if [ ! -z $1 ]; then
		SERVERCONFIG=$1
	fi

	echo $SERVERCONFIG

	paster serve $SERVERCONFIG &

	echo $! > $PIDPATH
}

stopsrv()
{
	if [ -e $PIDPATH ]; then
		kill -KILL $(cat $PIDPATH)

		rm $PIDPATH
	else
		echo "$0: The server is not running"
	fi
}

adduser()
{
	if [ ! -z $1 ]; then
		read -sp "Enter password for $1: " PASS

		SALT=$(openssl rand -hex 8)
		HASH=$(echo -n "$1$PASS$SALT" | sha256sum | sed 's/[ ]*-$//')$SALT

		if [ ! -e $AUTHDBPATH ]; then
			sqlite3 $AUTHDBPATH 'CREATE TABLE auth (user VARCHAR PRIMARY KEY, hash VARCHAR)'
		fi

		sqlite3 $AUTHDBPATH "INSERT INTO auth VALUES ('$1', '$HASH')"

		mkdir -p "collections/$1"
		unset PASS SALT HASH

		echo
	else
		usage
	fi
}

deluser()
{
	if [ ! -z $1 ] && [ -e $AUTHDBPATH ]; then
		sqlite3 $AUTHDBPATH "DELETE FROM auth WHERE user='$1'"
	elif [ -z $1 ]; then
		usage
	else
		echo "$0: Database file does not exist"
	fi
}

passwd()
{
	if [ -e $AUTHDBPATH ]; then
		read -sp "Enter password for $1: " PASS

		SALT=$(openssl rand -hex 8)
		HASH=$(echo -n "$1$PASS$SALT" | sha256sum | sed 's/[ ]*-$//')$SALT

		sqlite3 $AUTHDBPATH "UPDATE auth SET hash='$HASH' WHERE user='$1'"

		unset PASS SALT HASH

		echo
	else
		echo "$0: Database file does not exist"
	fi
}

main()
{
	[[ $1 ]] || usage

	case "$1" in
		'start') startsrv $2 ;;
		'stop') stopsrv ;;
		'adduser') adduser $2 ;;
		'deluser') deluser $2 ;;
		'passwd') passwd $2 ;;
		*) usage
	esac

	exit 0
}

main $@
