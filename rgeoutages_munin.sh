#!/bin/bash

BASEDIR=/var/www/hoopycat.com/html/rgeoutages

if [ "$1" = "config" ]; then
    cat <<EOM
graph_title RG&E Power Outage Summary
graph_args --base 1000 -l 0
graph_vlabel outages
graph_category Climate
customers.draw AREA
customers.label customers without power
outages.draw LINE
outages.label streets affected
EOM

elif [ "$1" = "autoconf" ]; then
    if [ -f $BASEDIR/fetch_outages.sh ]; then
        echo "yes"
    else
        echo "no"
    fi

else
    customercount=`/usr/local/bin/json_xs -t yaml < $BASEDIR/data.json | grep CustomersWithoutPower | awk '{ sum += $2 }; END { print sum }'`
    outagecount=`/usr/local/bin/json_xs < $BASEDIR/history.json | grep -c "  "`
    echo "customers.value $customercount"
    echo "outages.value $outagecount"
fi

