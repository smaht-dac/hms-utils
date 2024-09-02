#!/bin/bash

# Wrapper script for the poetry script hms-config (which is implemented in hms_config.py), to
# allow setting (export-ing) environment variables from the calling process. To use this from
# a shell script file which you wish to execute (or source), you need to put this at the top:
#
#    source $(hms-config --functions)
#
# And then in this script file you can do:
#
#    hms_config_exports \
#        auth0/local/Auth0Client \
#        auth0/local/Auth0Secret \
#        etc...
#
# And it will lookup those paths in your ~/.config/hms/config.json and secrets.json
# and will cause your environment variables for those (base) names (e.g. Auth0Client)
# to be set for the file, or for your environment (terminal session) if you source it.
# If you want different names the do it like this:
#
#    hms_config_exports \
#        AUTH0_CLIENT_ID:auth0/local/Auth0Client \
#        AUTH0_SECRET:auth0/local/Auth0Secret \
#        etc...
#
__HMS_CONFIG_SCRIPT=hms-config
function hms_config_exports() {
    __HMS_CONFIG_TMPFILE=/tmp/.hms_config-$RANDOM$RANDOM-`date +%Y%m%d%H%M%S`
    $__HMS_CONFIG_SCRIPT --export-file $__HMS_CONFIG_TMPFILE $*
    hms_config_status=$?
    if [ -f $__HMS_CONFIG_TMPFILE ] ; then
        source $__HMS_CONFIG_TMPFILE
        rm -f $__HMS_CONFIG_TMPFILE
    fi
}
function hms_config_export() {
    hms_config_exports $*
}
function hms_config() {
    $__HMS_CONFIG_SCRIPT $*
    hms_config_status=$?
}
