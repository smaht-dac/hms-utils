#!/bin/bash

# Wrapper script for the poetry script hms-config (which is implemented in hmsconfig.py), to
# allow setting (export-ing) environment variables from the calling process. To use this from
# a shell script file which you wish to execute (or source), you need to put this at the top:
#
#    source $(hms-config --functions)
#
# And then in this script file you can do:
#
#    hmsconfig_exports \
#        auth0/local/Auth0Client \
#        auth0/local/Auth0Secret \
#        etc...
#
# And it will lookup those paths in your ~/.config/hms/config.json and secrets.json
# and will cause your environment variables for those (base) names (e.g. Auth0Client)
# to be set for the file, or for your environment (terminal session) if you source it.
# If you want different names the do it like this:
#
#    hmsconfig_exports \
#        AUTH0_CLIENT_ID:auth0/local/Auth0Client \
#        AUTH0_SECRET:auth0/local/Auth0Secret \
#        etc...
#
function hmsconfig_exports() {
    for arg in "$@"; do
        if [[ "$arg" == "--debug" || "$arg" == "-debug" ]]; then
            __HMS_CONFIG_DEBUG=true
            break
        fi
    done
    __HMS_CONFIG_TMPFILE=/tmp/.hmsconfig-$RANDOM$RANDOM-`date +%Y%m%d%H%M%S`
    hmsconfig --export-file $__HMS_CONFIG_TMPFILE $*
    hms_config_status=$?
    if [ -f $__HMS_CONFIG_TMPFILE ] ; then
        source $__HMS_CONFIG_TMPFILE
        if [ "$__HMS_CONFIG_DEBUG" != "true" ] ; then
            rm -f $__HMS_CONFIG_TMPFILE
        fi
    fi
    unset __HMS_CONFIG_TMPFILE
    unset __HMS_CONFIG_DEBUG
}
function hmsconfig_export() {
    hmsconfig_exports $*
}
function hmsconfig() {
    hmsconfig $*
    hmsconfig_status=$?
}
