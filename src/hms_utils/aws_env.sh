#!/bin/bash
DIR=`realpath $(dirname $BASH_SOURCE)`

# Wrapper script to aws_env.py (which manages SSO/Okta-based AWS credentials in ~/.aws/config),
# to allow the --current option to actually work WRT setting the AWS_PROFILE environment
# variable from the calling (command-line/shell) process; since simply running a (Python)
# cannot set environment variables from the calling (command-line-shell) process.
# To use this you need to put an alias like this is your ~/.bash_profile or whatever:
# alias awsenv='source ~/repos/c4-scripts/dmichaels/scripts/aws_env.sh'
# The fact that it is an alias, and the 'source' there, is crucial to allow
# your AWS_PROFILE environment variable to be set (or unset for nocurrent).
# Then use according to the usage notes in aws_env.py, e.g.:
#
# usage: awsenv [profile-name-pattern] [nocheck]
#        awsenv default [profile-name] | awsenv nodefault
#        awsenv current [profile-name] | awsenv nocurrent
#        awsenv refresh [profile-name]

SCRIPTDIR=~/repos/hms-utils/src/hms_utils
SCRIPT="python $SCRIPTDIR/aws_env.py"
TMPFILE=/tmp/.aws_env-$RANDOM$RANDOM-`date +%Y%m%d%H%M%S`
$SCRIPT --current-export-file $TMPFILE $*
STATUS=$?
if [ -f $TMPFILE ] ; then
    source $TMPFILE
    rm -f $TMPFILE
    $SCRIPT --post-current-export-file $*
    STATUS=$?
fi
return $STATUS
