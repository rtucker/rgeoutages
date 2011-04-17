#!/bin/bash

BASEDIR=/var/www/hoopycat.com/html/rgeoutages/
GENERATOR=$BASEDIR/generate_map.py
HTMLFILE=$BASEDIR/index.html
export TZ=America/New_York

# Test for sanity
[ -d "$BASEDIR" ] || (echo "Base directory missing: $BASEDIR"; exit 1)
[ -x "$GENERATOR" ] || (echo "Generator script not executable: $GENERATOR"; exit 1)

# All together now
cd $BASEDIR
TEMPFILE=`tempfile`
$GENERATOR > $TEMPFILE

if [ -n "`cat $TEMPFILE`" ]; then
    cp $TEMPFILE $HTMLFILE
else
    echo "$TEMPFILE was empty, utoh"
fi

rm $TEMPFILE
