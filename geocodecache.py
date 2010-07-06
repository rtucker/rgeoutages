#!/usr/bin/python

import math
import sqlite3
import sys
import time
import urllib
import urllib2

try:
    import json
except:
    import simplejson as json

try:
    import secrets
except:
    sys.stderr.write("You need to create a secrets.py file with a Google Maps API key.")
    sys.exit(1)

def initDB(filename="rgeoutages.sqlite3"):
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
    jsondict = json.loads(jsondata)

    if jsondict['results'] == []:
        raise Exception("Empty results string: " + jsondict['status'])

    data = jsondict['results'][0]
    
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

def distance_on_unit_sphere(lat1, long1, lat2, long2):
    # From http://www.johndcook.com/python_longitude_latitude.html

    # Convert latitude and longitude to 
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0
        
    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians
        
    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians
        
    # Compute spherical distance from spherical coordinates.
        
    # For two locations in spherical coordinates 
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) = 
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length
    
    cos = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) + 
           math.cos(phi1)*math.cos(phi2))
    arc = math.acos( cos )

    # Remember to multiply arc by the radius of the earth 
    # in your favorite set of units to get length.
    return arc

def produceMapHeader(apikey, markers, centers, points):
    """Produces a map header given an API key and a list of produceMarkers"""

    out = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml">
  <head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
    <meta http-equiv="refresh" content="600"/>
    <title>Current Power Outage Map for Rochester, New York</title>
<style type="text/css">
    v\:* {behavior:url(#default#VML);}  html, body {width: 100%%; height: 100%%}  body {margin-top: 0px; margin-right: 0px; margin-left: 0px; margin-bottom: 0px}

    p, li {
        font-family:  Verdana, sans-serif;
        font-size: 13px;
      }

    a {
        text-decoration: none;
      }

    .hidden { visibility: hidden; }
    .unhidden { visibility: visible; }

</style>
<script src="http://maps.google.com/maps?file=api&amp;v=2&amp;key=%s" type="text/javascript"></script>
<script src="http://gmaps-utility-library.googlecode.com/svn/trunk/markermanager/release/src/markermanager.js"></script>
<script type="text/javascript">

    function hide(divID) {
        var item = document.getElementById(divID);
        if (item) {
            item.className=(item.className=='unhidden')?'hidden':'unhidden';
        }
    }

    function unhide(divID) {
        var item = document.getElementById(divID);
        if (item) {
            item.className=(item.className=='hidden')?'unhidden':'hidden';
        }
    }

    var map = null;
    var mgr = null;

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

    # Determine center of map:
    # Initialize variables
    minLat = 43.15661
    maxLat = 43.15661
    minLng = -77.6253
    maxLng = -77.6253

    # Iterate through and expand the range, ignoring outliers
    for i in points:
        if distance_on_unit_sphere((minLat+maxLat)/2, (minLng+maxLng)/2, i['latitude'], i['longitude'])*3960 < 50:
            minLat = min(i['latitude'], minLat)
            maxLat = max(i['latitude'], maxLat)
            minLng = min(i['longitude'], minLng)
            maxLng = max(i['longitude'], maxLng)

    # Calculate center
    centerLat = (minLat + maxLat) / 2
    centerLng = (minLng + maxLng) / 2

    # Guestimate zoom by finding diagonal distance (in miles)
    distance = distance_on_unit_sphere(minLat, minLng, maxLat, maxLng) * 3960
    if distance < 5:
        zoom = 15
    elif distance < 7:
        zoom = 14
    elif distance < 11:
        zoom = 13
    elif distance < 13:
        zoom = 12
    elif distance < 25:
        zoom = 11
    elif distance < 35:
        zoom = 10
    else:
        zoom = 9

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
        zoom = min(zoom, 11)
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
    /* distance: %.2f
       minimum corner: %.4f, %.4f
       maximum corner: %.4f, %.4f */
    """ % (distance, minLat, minLng, maxLat, maxLng)

    out += """
    function initialize() {
        if (GBrowserIsCompatible()) {
            map = new GMap2(document.getElementById("map_canvas"));
            map.setCenter(new GLatLng(%.4f, %.4f), %i);
            map.setUIToDefault();
            mgr = new MarkerManager(map);
            window.setTimeout(setupMarkers, 0);

            // Monitor the window resize event and let the map know when it occurs
            if (window.attachEvent) { 
                window.attachEvent("onresize", function() {this.map.onResize()} );
            } else {
                window.addEventListener("resize", function() {this.map.onResize()} , false);
            }
        }
    } """ % (centerLat, centerLng, zoom)

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
    <div id="map_canvas" style="width: 100%%; height: 100%%;"></div>
    %s
  </body>
</html>
""" % body

if __name__ == '__main__':
    db = initDB()
    try:
        apikey = secrets.apikey
    except:
        apikey = 'FIXME FIXME FIXME'

    localelist = []
    markerlist = []
    citycenterlist = []
    pointlist = []

    stoplist = ['HONEOYE%20FL', 'HONEOYE', 'N%20CHILI']

    for i in sys.argv[1:]:
        if i in stoplist:
            continue

        fd = open('outages_%s.txt' % i)
        lastupdated = fd.readline()
        cleanname = i.replace('%20', ' ')

        count = 0

        citycenter = geocode(db, cleanname, '')
        citycenterlist.append(produceMarker(citycenter['latitude'], citycenter['longitude'], citycenter['formattedaddress']))
        pointlist.append(citycenter)

        for j in fd.readlines():
            try:
                streetinfo = geocode(db, cleanname, j)
                markerlist.append(produceMarker(streetinfo['latitude'], streetinfo['longitude'], streetinfo['formattedaddress']))
                pointlist.append(streetinfo)
                count += 1
            except Exception, e:
                sys.stdout.write("<!-- Geocode fail: %s in %s gave %s -->\n" % (j, cleanname, e.__str__()))

        if count > 1:
            s = 's'
        else:
            s = ''

        localelist.append('<a href="http://ebiz1.rge.com/cusweb/outage/roadOutages.aspx?town=%s">%s</a>:&nbsp;%i&nbsp;street%s' % (i, cleanname, count, s))

    if len(markerlist) > 0:
        if len(markerlist) > 300:
            s = 's -- zoom for more detail'
        elif len(markerlist) > 1:
            s = 's'
        else:
            s = ''
        sys.stdout.write(produceMapHeader(apikey, markerlist, citycenterlist, pointlist))

        bodytext = """
            <div id="infobox" class="unhidden" style="top:25px; left:75px; position:absolute; background-color:white; border:2px solid black; width:50%%; opacity:0.8">
                <div id="closebutton" style="top:2px; right:2px; position:absolute">
                    <a href="javascript:hide('infobox');"><img src="xbox.png" border=0 alt="X" title="We'll leave the light on for you."></a>
                </div>
                <p><b>Map of Rochester-area Power Outages</b> as of %s (%i street%s).  <a href="javascript:unhide('faqbox');">More info</a>,
                      <a href="javascript:unhide('chartbox');">power outage graph</a></p>.
                <p style="font-size:xx-small;">%s</p>
            </div>

            <div id="faqbox" class="hidden" style="top:45px; left:95px; position:absolute; background-color:white; border:2px solid black; width:75%%">
                <div id="closebutton" style="top:2px; right:2px; position:absolute">
                    <a href="javascript:hide('faqbox');"><img src="xbox.png" border=0 alt="X" title="OK, OK, I'll show you the map."></a>
                </div>
                <p><b>IF YOU HAVE A LIFE-THREATENING ELECTRICAL EMERGENCY, CALL RG&E AT 1-800-743-1701 OR CALL 911 IMMEDIATELY.  DO NOT TOUCH DOWNED ELECTRICAL LINES, EVER.  EVEN IF YOUR STREET IS LISTED HERE.</b></p>
                <hr>
                <p>The source data for this map is published by <A HREF="http://ebiz1.rge.com/cusweb/outage/index.aspx">RG&E</A>, but all map-related blame should go to <a href="http://hoopycat.com/~rtucker/">Ryan Tucker</a> &lt;<a href="mailto:rtucker@gmail.com">rtucker@gmail.com</a>&gt;.  You can find the source code <a href="http://github.com/rtucker/rgeoutages/">on GitHub</a>.</p>
                <p>Some important tips to keep in mind...</p>
                <ul>
                    <li><b>RG&E only publishes a list of street names.</b> This map's pointer will end up in the geographic center of the street, which will undoubtedly be wrong for really long streets.  Look for clusters of outages.</li>
                    <li><b>This map doesn't indicate the actual quantity of power outages or people without power.</b> There may be just one house without power on a street, or every house on a street.  There may be multiple unrelated outages on one street, too.  There's no way to know.</li>
                </ul>
                <p>Also, be sure to check out RG&E's <a href="http://rge.com/Outages/">Outage Central</a> for official information, to report outages, or to check on the status of an outage.</p>
            </div>

            <div id="chartbox" class="hidden" style="top:45px; left:95px; position:absolute; background-color:white; border:2px solid black; width:500px">
                <div id="closebutton" style="top:2px; right:2px; position:absolute">
                    <a href="javascript:hide('chartbox');"><img src="xbox.png" border=0 alt="X" title="That was then; this is now."></a>
                </div>
                <img src="outagechart.png" title="Graph may be out of date by many hours.">
            </div>

        """ % (lastupdated, len(markerlist), s, '; '.join(localelist))

        sys.stdout.write(produceMapBody(bodytext))
 
