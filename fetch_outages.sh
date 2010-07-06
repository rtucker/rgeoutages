#!/bin/bash

BASEDIR=/var/www/hoopycat.com/html/rgeoutages/
GENERATOR=$BASEDIR/geocodecache.py
HTMLFILE=$BASEDIR/index.html

# Test for sanity
[ -d "$BASEDIR" ] || (echo "Base directory missing: $BASEDIR"; exit 1)
[ -x "$GENERATOR" ] || (echo "Generator script not executable: $GENERATOR"; exit 1)

# Fetch location list
TEMPFILE=`tempfile`
wget -q -O $TEMPFILE http://ebiz1.rge.com/cusweb/outage/index.aspx

LOCATIONS=`grep "<option value=\"14|" $TEMPFILE | cut -d'|' -f2 | cut -d'"' -f1 | sed "s/ /%20/g" | xargs`

rm $TEMPFILE

# Fetch street data
cd $BASEDIR || (echo "Could not cd to $BASEDIR"; exit 1)
rm outages_*.txt 2>/dev/null

for i in $LOCATIONS
do
    TEMPFILE=`tempfile`
    OUTFILE=outages_$i.txt
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
elif [ -z "$LOCATIONS" ] ; then
    # there are no outages!  do something cool.
    true
else
    echo "$TEMPFILE was empty, utoh"
fi

rm $TEMPFILE

# Fetch a munin chart
wget -q -O outagechart.png http://hennepin.hoopycat.com/munin/hoopycat.com/framboise-rgeoutages-day.png

