#! /usr/bin/env bash

export PYTHONPATH="/usr/share/ankisyncd"
export PYTHON="python"

if [ $(python -V 2>&1 | cut -d ' ' -f 2  | cut -d '.'  -f 1) -ne 2 ]; then
	which python2 > /dev/null

	if [ $? -eq 0 ]; then
		PYTHON="python2"
	else
		echo "$0: Cannot find Python 2" 1>&2
	fi
fi

$PYTHON /usr/share/ankisyncd/ankisyncd/sync_app.py
