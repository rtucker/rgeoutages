#!/bin/bash

GENERATOR=/var/www/hoopycat.com/html/rgeoutages/geocodecache.py
HTMLFILE=/var/www/hoopycat.com/html/rgeoutages/index.html

# Fetch location list
TEMPFILE=`tempfile`
wget -q -O $TEMPFILE http://ebiz1.rge.com/cusweb/outage/index.aspx

LOCATIONS=`grep "<option value=\"14|" $TEMPFILE | cut -d'|' -f2 | cut -d'"' -f1 | sed "s/ /%20/g" | xargs`

rm $TEMPFILE

for i in $LOCATIONS
do
    TEMPFILE=`tempfile`
    OUTFILE=/var/www/hoopycat.com/html/rgeoutages/outages_$i.txt
    wget -q -O $TEMPFILE "http://ebiz1.rge.com/cusweb/outage/roadoutages.aspx?town=$i"
    grep "wcHeader_Label3" $TEMPFILE \
     | cut -d'>' -f2 | cut -d'<' -f1 > $OUTFILE
    grep "<td nowrap=\"nowrap\">" $TEMPFILE \
     | cut -d">" -f2 | cut -d"<" -f1 >> $OUTFILE
    rm $TEMPFILE
    sleep 2
done

# All together now
TEMPFILE=`tempfile`

$GENERATOR $LOCATIONS > $TEMPFILE

if [ -n "`cat $TEMPFILE`" ]; then
    cp $TEMPFILE $HTMLFILE
    rm $TEMPFILE
elif [ -z "$LOCATIONS" ] ; then
    # there are no outages!  do something cool.
    true
else
    echo "$TEMPFILE was empty, utoh"
fi

