#!/bin/bash

URL="http://ebiz1.rge.com/cusweb/outage/roadOutages.aspx?town=ROCHESTER"
TEMPFILE=`tempfile`
OUTFILE=/var/www/hoopycat.com/html/rgeoutages/outages_rochester.txt
GENERATOR=/var/www/hoopycat.com/html/rgeoutages/geocodecache.py
HTMLFILE=/var/www/hoopycat.com/html/rgeoutages/index.html

wget -q -O $TEMPFILE $URL

grep "wcHeader_Label3" $TEMPFILE \
 | cut -d'>' -f2 | cut -d'<' -f1 > $OUTFILE

grep "<td nowrap=\"nowrap\">" $TEMPFILE \
 | cut -d">" -f2 | cut -d"<" -f1 >> $OUTFILE

$GENERATOR > $TEMPFILE

if [ -n "`cat $TEMPFILE`" ]; then
    cp $TEMPFILE $HTMLFILE
else
    echo "$TEMPFILE was empty, utoh"
fi

