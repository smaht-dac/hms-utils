#!/bin/bash
DIR=`realpath $(dirname $BASH_SOURCE)`

# Wrapper script for the poetry script hms-config (which is implement in hms_config.py),
# to allow setting environment variables from the calling process.
# To use this you need to put an alias like this is your ~/.bash_profile or wherever:
#
# >>> alias config='source `hms-config --shell`'
#
SCRIPT=hms-config
TMPFILE=/tmp/.hms_config-$RANDOM$RANDOM-`date +%Y%m%d%H%M%S`
$SCRIPT --export-file $TMPFILE $*
STATUS=$?
if [ -f $TMPFILE ] ; then
    source $TMPFILE
    rm -f $TMPFILE
fi
return $STATUS
