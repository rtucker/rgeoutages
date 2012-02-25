#!/usr/bin/python

# Scrapes RG&E outage information.
# Requires:
#   python-pycurl
#   python-beautifulsoup

import os
import pycurl
import StringIO

from BeautifulSoup import BeautifulSoup

BASE_URL="http://www3.rge.com/OutageReports/"
START_URL="RGE.html"

try:
    GIT_VERSION = open('.git/refs/heads/master','r').read().strip()
    GIT_MODTIME = os.stat('.git/refs/heads/master').st_mtime
except IOError:
    GIT_MODTIME = GIT_VERSION = "dev"

USERAGENT="rgeoutages/%s (http://hoopycat.com/rgeoutages/; version %s)" % (GIT_MODTIME, GIT_VERSION)

def get_url(url):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, str(url))
    c.setopt(pycurl.USERAGENT, USERAGENT)
    b = StringIO.StringIO()
    c.setopt(pycurl.WRITEFUNCTION, b.write)
    c.perform()
    b.seek(0)
    return b

def clean_int(num):
    return int(num.replace(',', ''))

def scrape_table(table):
    data = {}
    headings = []

    for row in table('tr'):
        if row.th:
            if len(row('th')) > 1 and str(row.th.string) != str('&nbsp;'):
                headings = [cell.renderContents() for cell in row('th')]
        elif row.td:
            contents = [cell.renderContents() for cell in row('td')]
            href = None
            if row('td')[0].a:
                for attr in row('td')[0].a.attrs:
                    if attr[0] == 'href':
                        href = attr[1]
                contents[0] = row('td')[0].a.contents[0]
            if href:
                data[href] = contents
            elif not contents[0].startswith('&'):
                data[contents[0]] = contents[1:]

    return (headings, data)

def get_soup(url):
    content = get_url(url).readlines()
    return BeautifulSoup(''.join(content))

def crawl_outages(base_url=BASE_URL, start_url=START_URL):
    outages = {}

    # Get bunch of counties
    countysoup = get_soup(base_url + start_url)
    countyheadings, countydata = scrape_table(countysoup.table)

    # From here, we need to get a bunch of townships...
    for countyfile, countyrow in countydata.items():
        if countyfile.startswith('http'):
            # It isn't our normal relative URL; ignore it
            continue
        countydict = {}

        townsoup = get_soup(base_url + countyfile)
        townheadings, towndata = scrape_table(townsoup.table)

        # And then a bunch of locations...
        for townfile, townrow in towndata.items():
            if str(townfile) == str(start_url):
                continue
            towndict = {}

            locationsoup = get_soup(base_url + townfile)
            locationheadings, locationdata = scrape_table(locationsoup.table)
                   
            # And then a bunch of streets...
            for locationfile, locationrow in locationdata.items():
                if str(locationfile) == str(start_url):
                    continue
                locationdict = {}
                streetsoup = get_soup(base_url + locationfile)
                streetheadings, streetdata = scrape_table(streetsoup.table)
                for streetname, streetrow in streetdata.items():
                    if str(streetname) == str(countyfile):
                        continue
                    if str(streetname).lower().endswith('html'): continue

                    if len(streetrow) == 2:
                        streetrow.append('Unknown')

                    locationdict[streetname] = {
                        'TotalCustomers': clean_int(streetrow[0]),
                        'CustomersWithoutPower': clean_int(streetrow[1]),
                        'EstimatedRestoration': streetrow[2],
                        }

                if len(locationrow) < 3: continue
                towndict[locationrow[0]] = {
                    'TotalCustomers': clean_int(locationrow[1]),
                    'CustomersWithoutPower': clean_int(locationrow[2]),
                    'Streets': locationdict,
                    }

            countydict[townrow[0]] = {
                'TotalCustomers': clean_int(townrow[1]),
                'CustomersWithoutPower': clean_int(townrow[2]),
                'Locations': towndict,
                }

        outages[countyrow[0]] = {
            'TotalCustomers': clean_int(countyrow[1]),
            'CustomersWithoutPower': clean_int(countyrow[2]),
            'Towns': countydict,
            }

    return outages

if __name__ == '__main__':
    structure = crawl_outages(BASE_URL, START_URL)
    print `structure`
