#!/usr/bin/python

import sqlite3
import sys
import time
import urllib
import urllib2

try:
    import json
except:
    import simplejson as json

def initDB(filename="/tmp/rgeoutages.sqlite3"):
    """Connect to and initialize the cache database.

    Optional: Filename of database
    Returns: db object
    """

    db = sqlite3.connect(filename)
    c = db.cursor()
    c.execute('pragma table_info(geocodecache)')
    columns = ' '.join(i[1] for i in c.fetchall()).split()
    if columns == []:
        # need to create table
        c.execute("""create table geocodecache
            (town text, streetname text, latitude real, longitude real,
             formattedaddress text, locationtype text, lastcheck integer,
             viewport text)""")
        db.commit()

    return db

def fetchGeocode(location):
    """Fetches geocoding information.

    Returns dictionary of formattedaddress, latitude, longitude,
    locationtype, and viewport tuple of (sw_lat, sw_lng, ne_lat, ne_lng).
    """

    sanelocation = urllib.quote(location)

    response = urllib2.urlopen("http://maps.google.com/maps/api/geocode/json?address=%s&sensor=false" % sanelocation)

    jsondata = response.read()
    data = json.loads(jsondata)['results'][0]
    
    viewport = (    data['geometry']['viewport']['southwest']['lat'],
                    data['geometry']['viewport']['southwest']['lng'],
                    data['geometry']['viewport']['northeast']['lat'],
                    data['geometry']['viewport']['northeast']['lng']    )
    outdict = { 'formattedaddress': data['formatted_address'],
                'latitude': data['geometry']['location']['lat'],
                'longitude': data['geometry']['location']['lng'],
                'locationtype': data['geometry']['location_type'],
                'viewport': viewport    }

    time.sleep(1)

    return outdict

def geocode(db, town, location):
    """Geocodes a location, either using the cache or the Google.

    Returns dictionary of formattedaddress, latitude, longitude,
    locationtype, and viewport tuple of (sw_lat, sw_lng, ne_lat, ne_lng).
    """

    town = town.lower().strip()
    location = location.lower().strip()

    using_cache = False

    # check the db
    c = db.cursor()
    c.execute('select latitude,longitude,formattedaddress,locationtype,viewport,lastcheck from geocodecache where town=? and streetname=? order by lastcheck desc limit 1', (town, location))

    rows = c.fetchall()
    if rows:
        (latitude,longitude,formattedaddress,locationtype,viewport_json,lastcheck) = rows[0]
        if lastcheck < (time.time()+(7*24*60*60)):
            using_cache = True
            viewport = tuple(json.loads(viewport_json))

            outdict = { 'formattedaddress': formattedaddress,
                        'latitude': latitude,
                        'longitude': longitude,
                        'locationtype': locationtype,
                        'viewport': viewport    }
            return outdict

    if not using_cache:
        fetchresult = fetchGeocode(location + ", " + town + " NY")

        viewport_json = json.dumps(fetchresult['viewport'])

        c.execute('insert into geocodecache (town, streetname, latitude, longitude, formattedaddress, locationtype, lastcheck, viewport) values (?,?,?,?,?,?,?,?)', (town, location, fetchresult['latitude'], fetchresult['longitude'], fetchresult['formattedaddress'], fetchresult['locationtype'], time.time(), viewport_json))
        db.commit()

        return fetchresult

def produceMapHeader(apikey, markers, centers):
    """Produces a map header given an API key and a list of produceMarkers"""

    out = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml">
  <head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
    <title>Current Power Outage Map for Rochester, New York</title>
<script src="http://maps.google.com/maps?file=api&amp;v=2&amp;key=%s" type="text/javascript"></script>
<script src="http://gmaps-utility-library.googlecode.com/svn/trunk/markermanager/release/src/markermanager.js"></script>
<script type="text/javascript">

    var map = null;
    var mgr = null;

    function initialize() {
        if (GBrowserIsCompatible()) {
            map = new GMap2(document.getElementById("map_canvas"));
            map.setCenter(new GLatLng(43.15661, -77.6253), 11);
            map.setUIToDefault();
            mgr = new MarkerManager(map);
            window.setTimeout(setupMarkers, 0);
        }
    }

    function createMarker(point, text) {
        var baseIcon = new GIcon(G_DEFAULT_ICON);
        baseIcon.shadow = "http://www.google.com/mapfiles/shadow50.png";
        baseIcon.iconSize = new GSize(20, 34);
        baseIcon.shadowSize = new GSize(37, 34);
        baseIcon.iconAnchor = new GPoint(9, 34);
        baseIcon.infoWindowAnchor = new GPoint(9, 2);

        var ouricon = new GIcon(baseIcon);
        ouricon.image = "http://www.google.com/mapfiles/marker.png";

        // Set up our GMarkerOptions object
        markerOptions = { icon:ouricon };
        var marker = new GMarker(point, markerOptions);

        GEvent.addListener(marker, "click", function() {
            marker.openInfoWindowHtml(text);
        });
        return marker;
    }

""" % apikey

    if len(markers) > 300:
        out += """
            function setupMarkers() {
                var batch = [];
                %s
                mgr.addMarkers(batch, 12);
                var batch = [];
                %s
                mgr.addMarkers(batch, 1, 12);
                mgr.refresh();
            }
        """ % ('\n'.join(markers), '\n'.join(centers))
    else:
        out += """
            function setupMarkers() {
                var batch = [];
                %s
                mgr.addMarkers(batch, 1);
                mgr.refresh();
            }
        """ % '\n'.join(markers)

    out += """
        </script>
        </head>
    """

    return out

def produceMarker(lat, long, text):
    """Produces a google maps marker given a latitude, longitude, and text"""
    return 'batch.push(new createMarker(new GLatLng(%f, %f), "%s"));' % (lat, long, text)

def produceMapBody(body):
    return """  <body onload="initialize()" onunload="GUnload()">
    %s
    <div id="map_canvas" style="height: 500px;"></div>
  </body>
</html>
""" % body

if __name__ == '__main__':
    db = initDB()
    apikey = "ABQIAAAA30Jhq_DCCBUDYXZhoCyheRSUYQ6bykvEQfbcB8o1clNVPLJCmBS95D0ZW-pGwa1P39Qz-hMw8rGwxA"

    localelist = []
    markerlist = []
    citycenterlist = [] 

    stoplist = ['HONEOYE%20FL', 'HONEOYE', 'N%20CHILI']

    for i in sys.argv[1:]:
        if i in stoplist:
            continue

        fd = open('/var/www/hoopycat.com/html/rgeoutages/outages_%s.txt' % i)
        lastupdated = fd.readline()
        cleanname = i.replace('%20', ' ')

        count = 0

        citycenter = geocode(db, cleanname, '')
        citycenterlist.append(produceMarker(citycenter['latitude'], citycenter['longitude'], citycenter['formattedaddress']))

        for j in fd.readlines():
            streetinfo = geocode(db, cleanname, j)
            markerlist.append(produceMarker(streetinfo['latitude'], streetinfo['longitude'], streetinfo['formattedaddress']))
            count += 1

        if count > 1:
            s = 's'
        else:
            s = ''

        localelist.append('<a href="http://ebiz1.rge.com/cusweb/outage/roadOutages.aspx?town=%s">%s</a>: %i street%s' % (i, cleanname, count, s))

    if len(markerlist) > 0:
        sys.stdout.write(produceMapHeader(apikey, markerlist, citycenterlist))
        sys.stdout.write(produceMapBody('<p>Rochester-area Power Outages, Last updated: %s, %i objects.  Data courtesy <A HREF="http://ebiz1.rge.com/cusweb/outage/index.aspx">RG&E</A>, all blame to <a href="http://hoopycat.com/~rtucker/">Ryan Tucker</a> &lt;<a href="mailto:rtucker@gmail.com">rtucker@gmail.com</a>&gt;.</p><p style="font-size:xx-small;">%s</p>' % (lastupdated, len(markerlist), '; '.join(localelist))))


