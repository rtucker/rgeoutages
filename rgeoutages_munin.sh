#!/bin/bash

BASEDIR=/var/www/hoopycat.com/html/rgeoutages

if [ "$1" = "config" ]; then
    cat <<EOM
graph_title RG&E Power Outage Summary
graph_args --base 1000 -l 0
graph_vlabel outages
graph_category Climate
outages.draw AREA
outages.label outages
EOM

elif [ "$1" = "autoconf" ]; then
    if [ -f $BASEDIR/fetch_outages.sh ]; then
        echo "yes"
    else
        echo "no"
    fi

else
    outagecount=`/usr/local/bin/json_xs < $BASEDIR/history.json | grep -c "  "`
    echo "outages.value $outagecount"
fi

