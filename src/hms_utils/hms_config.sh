#!/bin/bash
DIR=`realpath $(dirname $BASH_SOURCE)`

# Wrapper script for the poetry script hms-config (which is implement in hms_config.py),
# to allow setting (export-ing) environment variables from the calling process.
# To use this from a file whic you wish to "source" you need to add this at the top:
#
#    source $(hms-config --function)
#
# And then in the file you can do:
#
#    hms_config auth0/local/Auth0Client auth0/local/Auth0Secret ...
#
function hms_config() {
    SCRIPT=hms-config
    TMPFILE=/tmp/.hms_config-$RANDOM$RANDOM-`date +%Y%m%d%H%M%S`
    $SCRIPT --export-file $TMPFILE $*
    STATUS=$?
    if [ -f $TMPFILE ] ; then
        source $TMPFILE
        rm -f $TMPFILE
    fi
    return $STATUS
}
