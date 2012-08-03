#!/bin/bash
LOGDIR=logs.run
if test -n "$1"; then
    LOGDIR="$1"
fi
fgrep "*********************** done" $LOGDIR/* | fgrep -v "done 0" | fgrep -v "done 15" | fgrep -v "done -3 " | fgrep -v "done -4 " | fgrep -v "done -5 " | fgrep -v "done 20" | fgrep -v all.log | sed -e "s/:.*//"

