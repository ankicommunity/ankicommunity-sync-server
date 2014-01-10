#! /usr/bin/env bash

export PYTHONPATH="/usr/share/ankisyncd"
export PYTHON="python2"

which python2 > /dev/null

if [ $? -ne 0 ]; then
        which python > /dev/null

        if [ $? -ne 0 -a \
        $($PYTHON -V 2>&1 | cut -d ' ' -f 2 | cut -d '.' -f 1) -ne 2 ]; then
                PYTHON="python"
        else
                echo "$0: Cannot find Python 2" 1>&2

                exit 1
        fi
fi

$PYTHON /usr/share/ankisyncd/ankisyncd/sync_app.py
