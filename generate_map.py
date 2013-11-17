#!/usr/bin/python
# vim: set fileencoding=utf-8 :

import math
import os
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

import scrape_rge

def initDB(filename="rgeoutages.sqlite3"):
    """Connect to and initialize the cache database.

    Optional: Filename of database
    Returns: db object
    """

    db = sqlite3.connect(filename)
    c = db.cursor()
    c.execute('pragma table_info(geocodecache2)')
    columns = ' '.join(i[1] for i in c.fetchall()).split()
    if columns == []:
        # need to create table
        c.execute("""create table geocodecache2
            (town text, location text, streetname text, latitude real,
             longitude real, formattedaddress text, locationtype text,
             lastcheck integer, viewport text)""")
        db.commit()

    return db

def fetchGeocode(location):
    """Fetches geocoding information.

    Returns dictionary of formattedaddress, latitude, longitude,
    locationtype, and viewport tuple of (sw_lat, sw_lng, ne_lat, ne_lng).
    """

    sanelocation = urllib.quote(location)

    response = urllib2.urlopen("http://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false" % sanelocation)

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

def geocode(db, town, location, street):
    """Geocodes a location, either using the cache or the Google.

    Returns dictionary of formattedaddress, latitude, longitude,
    locationtype, and viewport tuple of (sw_lat, sw_lng, ne_lat, ne_lng).
    """

    town = town.lower().strip()
    if location:
        location = location.lower().strip()
    else:
        location = town
    street = street.lower().strip()

    if street.endswith(' la'):
        street += 'ne'

    using_cache = False

    # check the db
    c = db.cursor()
    c.execute('select latitude,longitude,formattedaddress,locationtype,viewport,lastcheck from geocodecache2 where town=? and location=? and streetname=? order by lastcheck desc limit 1', (town, location, street))

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
        fetchresult = fetchGeocode(street + ", " + location + " NY")

        viewport_json = json.dumps(fetchresult['viewport'])

        c.execute('insert into geocodecache2 (town, location, streetname, latitude, longitude, formattedaddress, locationtype, lastcheck, viewport) values (?,?,?,?,?,?,?,?,?)', (town, location, street, fetchresult['latitude'], fetchresult['longitude'], fetchresult['formattedaddress'], fetchresult['locationtype'], time.time(), viewport_json))
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

    out = u"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml">
  <head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
    <meta http-equiv="refresh" content="900"/>
    <title>(%i) Rochester, New York Power Outage Map</title>
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
<script type="text/javascript" src="//maps.googleapis.com/maps/api/js?v=3&key=%s&sensor=false"></script>
<script type="text/javascript" src="markerclusterer.js"></script>
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

    function createMarker(map, infowindow, position, title, text, color) {
        var marker = new google.maps.Marker({
            title: title,
            position: position,
            icon: "//www.google.com/mapfiles/marker_" + color + ".png"
        });

        google.maps.event.addListener(marker, "click", function() {
            infowindow.content = text;
            infowindow.open(map, marker);
        });

        return marker;
    }

""" % (len(markers), apikey)

    # Determine center of map:
    # Initialize variables
    minLat = 44.9
    maxLat = 42.1
    minLng = -76.1
    maxLng = -78.9

    # Iterate through and expand the range, ignoring outliers
    for i in points:
        if distance_on_unit_sphere((minLat+maxLat)/2, (minLng+maxLng)/2, i['latitude'], i['longitude'])*3960 < 30:
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
    elif distance < 8:
        zoom = 13
    elif distance < 13:
        zoom = 12
    elif distance < 29:
        zoom = 11
    elif distance < 35:
        zoom = 10
    else:
        zoom = 9

    out += u"""
        function setupMarkers(map, infowindow) {
            var batch = [];
            %s
            return batch;
        }
    """ % '\n'.join(markers)

    out += u"""
    /* distance: %.2f
       minimum corner: %.4f, %.4f
       maximum corner: %.4f, %.4f */
    """ % (distance, minLat, minLng, maxLat, maxLng)

    out += u"""
    function initialize() {
        var map = new google.maps.Map(
            document.getElementById("map_canvas"), {
                center: new google.maps.LatLng(%.4f, %.4f),
                zoom: %i,
                mapTypeId: google.maps.MapTypeId.TERRAIN
        });

        var infowindow = new google.maps.InfoWindow({
            content: "lorem ipsum"
        });

        var markerCluster = new MarkerClusterer(map, setupMarkers(map, infowindow));
    };

    google.maps.event.addDomListener(window, 'load', initialize);

    """ % (centerLat, centerLng, zoom)
    out += u"""
        </script>
        </head>
    """

    return out

def produceMarker(lat, lng, text, firstreport=-1, streetinfo={}):
    """Produces a google maps marker given a latitude, longitude, text, and first report time"""
    color = 'grey'
    if firstreport > 0:
        age = time.time()-firstreport
        nicetime = time.asctime(time.localtime(firstreport))
        streetinfo['FirstReported'] = nicetime
        # colors available:
        # black, brown, green, purple, yellow, grey, orange, white
        if age < 15*60:
            color = 'white'
        elif age < 25*60:
            color = 'green'
        elif age < 35*60:
            color = 'yellow'
        elif age < 45*60:
            color = 'purple'
        elif age < 65*60:
            color = 'orange'
        elif age < 115*60:
            color = 'brown'
        else:
            color = 'black'

    longtext = '<strong>' + text + '</strong><br />' + '<br />'.join('%s: %s' % (key, value) for key, value in streetinfo.items())
    return 'batch.push(new createMarker(map, infowindow, new google.maps.LatLng(%f, %f), "%s", "%s", "%s"));' % (lat, lng, text, longtext, color)

def produceMapBody(body):
    return u"""  <body>
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

    git_version = open('.git/refs/heads/master','r').read()
    git_modtime = time.asctime(time.localtime(os.stat('.git/refs/heads/master').st_mtime))

    try:
        # open the history file (how long current outages have been there)
        historyfd = open('history.json','r')
        historydict = json.load(historyfd)
        historyfd.close()
    except IOError:
        historydict = {}
    newhistorydict = {}
    newjsondict = {}

    # fetch the outages
    outagedata = scrape_rge.crawl_outages()

    for county, countydata in outagedata.items():
        newjsondict[county] = {}
        towns = countydata['Towns']
        for town, towndata in towns.items():
            newjsondict[county][town] = {}
            locations = towndata['Locations']
            count = 0
            for location, locationdata in locations.items():
                streets = locationdata['Streets']
                newjsondict[county][town][location] = {}
                for street, streetdata in streets.items():
                    newjsondict[county][town][location][street] = {}
                    for key, value in streetdata.items():
                        newjsondict[county][town][location][street][key] = value
                    try:
                        streetinfo = geocode(db, town, location, street)
                        if streetinfo['formattedaddress'] in historydict.keys():
                            firstreport = historydict[streetinfo['formattedaddress']]
                        else:
                            firstreport = time.time()
                        if streetinfo['locationtype'] == 'APPROXIMATE':
                            streetinfo['formattedaddress'] = '%s? (%s)' % (street, streetinfo['formattedaddress'])
                        newjsondict[county][town][location][street]['geo'] = streetinfo
                        newjsondict[county][town][location][street]['firstreport'] = firstreport
                        markerlist.append(produceMarker(streetinfo['latitude'], streetinfo['longitude'], streetinfo['formattedaddress'], firstreport, streetdata))
                        pointlist.append(streetinfo)
                        newhistorydict[streetinfo['formattedaddress']] = firstreport
                        count += 1
                    except Exception, e:
                        sys.stdout.write("<!-- Geocode fail: %s in %s gave %s -->\n" % (street, town, e.__str__()))

            if count > 1:
                s = 's'
            else:
                s = ''

            citycenter = geocode(db, town, '', '')
            citycenterlist.append(produceMarker(citycenter['latitude'], citycenter['longitude'], citycenter['formattedaddress'] + ' (%i street%s)' % (count, s)))

            localestring = '<strong>%s</strong>:&nbsp;%i&nbsp;street%s' % (town, count, s)
            for key, value in towndata.items():
                if type(value) is not dict:
                    localestring += ',&nbsp;%s:&nbsp;%s' % (key, value)
            localestring += '&nbsp;(%.2f%%&nbsp;affected)' % (float(towndata['CustomersWithoutPower']) / float(towndata['TotalCustomers']) * 100.0)
            localelist.append(localestring)

    # Save json history file
    newhistoryfd = open('history.json','w')
    json.dump(newhistorydict, newhistoryfd)
    newhistoryfd.close()

    # Save json dump file
    newjsonfd = open('data.new.json','w')
    json.dump(newjsondict, newjsonfd)
    newjsonfd.close()
    os.rename('data.new.json', 'data.json')

    # XXX: DEBUG CODE
    if False:
        c = db.cursor()
        c.execute('select latitude,longitude,formattedaddress,locationtype,viewport,lastcheck from geocodecache2 where town=? order by lastcheck desc', ("rochester",))

        for i, r in enumerate(c.fetchall()):
            markerlist.append(produceMarker(r[0], r[1], r[2], i, {'debug': "num %d" % i}))
    # XXX: END DEBUG

    if len(markerlist) == 1:
        s = ''
    else:
        s = 's'

    sys.stdout.write(produceMapHeader(apikey, markerlist, citycenterlist, pointlist).encode("utf-8"))

    bodytext = u"""
        <div id="infobox" class="unhidden" style="top:25px; left:75px; position:absolute; background-color:white; border:2px solid black; width:50%%; opacity:0.8; padding:10px;">
            <div id="closebutton" style="top:2px; right:2px; position:absolute">
                <a href="javascript:hide('infobox');"><img src="xbox.png" border=0 alt="X" title="We'll leave the light on for you."></a>
            </div>
            <p><b>Rochester-area Power Outage Map</b> as of %s (%i street%s)</b></p>
            <p style="font-size:small;"><a href="javascript:unhide('faqbox');">More information about this map</a> | 
                  <a href="javascript:unhide('chartbox');">Outage graph</a> |
                  <a href="data.json">JSON</a></p>
            <p style="font-size:xx-small;">%s</p>
        </div>

        <div id="faqbox" class="hidden" style="top:45px; left:95px; position:absolute; background-color:white; border:2px solid black; width:75%%; padding:10px;">
            <div id="closebutton" style="top:2px; right:2px; position:absolute">
                <a href="javascript:hide('faqbox');"><img src="xbox.png" border=0 alt="X" title="OK, OK, I'll show you the map."></a>
            </div>
            <p>This map plots the approximate locations of power outages in Rochester, New York, and is updated every ten minutes.  The source data for this map is published by <A HREF="http://www.rge.com/Outages/outageinformation.html">RG&E</A>, but all map-related blame should go to <a href="http://hoopycat.com/~rtucker/">Ryan Tucker</a> &lt;<a href="mailto:rtucker@gmail.com">rtucker@gmail.com</a>&gt;.  You can find the source code <a href="https://github.com/rtucker/rgeoutages/">on GitHub</a>.</p>
            <p>Some important tips to keep in mind...</p>
            <ul>
                <li><b>RG&E only publishes a list of street names.</b> This map's pointer will end up in the geographic center of the street, which will undoubtedly be wrong for really long streets.  Look for clusters of outages.</li>
                <li><b>This map doesn't indicate the actual quantity of power outages or people without power.</b> There may be just one house without power on a street, or every house on a street.  There may be multiple unrelated outages on one street, too.  There's no way to know.</li>
                <li><b>This page may be out of date.</b> This page does not get regenerated if there are no outages.  (Pure laziness on my part.)  If in doubt, check the as-of time.</li>
            </ul>
            <p>Also, be sure to check out RG&E's <a href="http://rge.com/Outages/">Outage Central</a> for official information, to report outages, or to check on the status of an outage.</p>
            <hr>
            <p><b>IF YOU HAVE A LIFE-THREATENING ELECTRICAL EMERGENCY, CALL RG&E AT 1-800-743-1701 OR CALL 911 IMMEDIATELY.  DO NOT TOUCH DOWNED ELECTRICAL LINES, EVER.  EVEN IF YOUR STREET IS LISTED HERE.</b></p>
            <p style="font-size:xx-small;"><a href="https://github.com/rtucker/rgeoutages/commit/%s">Software last modified %s</a>.</p>
        </div>

        <div id="chartbox" class="hidden" style="top:45px; left:95px; position:absolute; background-color:white; border:2px solid black; padding:10px;">
            <div id="closebutton" style="top:2px; right:2px; position:absolute">
                <a href="javascript:hide('chartbox');"><img src="xbox.png" border=0 alt="X" title="Hide graph window"></a>
            </div>
            <div id="graphimage" style="background:url(http://munin.sodtech.net/hoopycat.com/framboise/rgeoutages-day.png); width:495px; height:271px;"></div>
        </div>

    """ % (time.asctime(), len(markerlist), s, '<br/>'.join(localelist), git_version, git_modtime)

    sys.stdout.write(produceMapBody(bodytext))
