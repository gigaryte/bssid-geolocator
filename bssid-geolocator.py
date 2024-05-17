#!/usr/bin/env python3
import os
import sys
import json
import logging
import argparse
import requests
import bssid_pb2
import simplekml
from urllib3.exceptions import InsecureRequestWarning

#suppress certificate warnings for hitting Apple's location services API
#endpoint
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)

def geolocateApple(bssid):
    '''
    @brief: Attempts to geolocate a BSSID using the Apple location services API
    @param: bssid: the BSSID to attempt to geolocate
    @returns: (lat,lon) tuple of floats

    @notes: much of this code borrowed from iSniff-GPS, who borrowed it from 
    Mostly taken from paper by François-Xavier Aguessy and Côme Demoustier
    http://fxaguessy.fr/rapport-pfe-interception-ssl-analyse-donnees-localisation-smartphones/
    '''

    logging.info(f"Geolocating bssid {bssid}")

    data_bssid = f"\x12\x13\n\x11{bssid}\x18\x00\x20\00"
    headers = {'Content-Type':'application/x-www-form-urlencoded',
                'Accept':'*/*', 
                "Accept-Charset": "utf-8",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language":"en-us", 
                'User-Agent':'locationd/1753.17 CFNetwork/711.1.12 Darwin/14.0.0'
                }  
    data = "\x00\x01\x00\x05en_US\x00\x13com.apple.locationd\x00\x0a"+\
           "8.1.12B411\x00\x00\x00\x01\x00\x00\x00" + \
           chr(len(data_bssid)) + data_bssid;

    r = requests.post('https://gs-loc.apple.com/clls/wloc',headers=headers,data=data,verify=False) # CN of cert on this hostname is sometimes *.ls.apple.com / ls.apple.com, so have to disable SSL verify

    bssidResponse = bssid_pb2.WiFiLocation()
    bssidResponse.ParseFromString(r.content[10:])

    geos = []

    for wifi in bssidResponse.wifi:
        #Skip any BSSIDs Apple returns that aren't the one we requested
        #Need to normalize each MAC byte because the string representation will
        #strip out leading 0s for some reason. So for e.g., need to turn 
        # 0:11:22:33:44:55
        # into 00:11:22:33:44:55
        paddedBSSID = ":".join("0" + x if len(x) == 1 else x for x in
                wifi.bssid.split(":"))
        lat = wifi.location.lat * pow(10,-8) 
        lon = wifi.location.lon * pow(10,-8)
        channel = wifi.channel
        hacc = wifi.location.hacc

        geos.append((paddedBSSID, f"{lat},{lon}", channel, hacc))

    return geos

def writeKML(locations, fname):
    '''
    @brief: Writes the KML output file if user wanted one written
    @param: locations: dictionary keyed by EUI-64-derived MAC address
    @return: None
    '''

    kml = simplekml.Kml()

    for res in locations:
        bssid = res[0]
        ll = res[1]
        lat = float(ll.split(',')[0])
        lon = float(ll.split(',')[1])

        #skip the default invalid coordinates we return if we can't find a
        #predicted BSSID
        if lat == -180 and lon == -180:
            continue

        point = kml.newpoint(name=bssid, description=f"{bssid}",
                coords=[(lon, lat)])

    kml.save(fname)

    return None

def main(args):

    locations = {}

    #Single bssid geolocation requested
    locations = geolocateApple(args.bssid)

    for location in locations:
        print(f"{' '.join([str(x) for x in location])}")

    if args.kml:
        writeKML(locations, args.kml)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("bssid", help="Single BSSID to geo")
    parser.add_argument("-k", "--kml", help="Output KML filename")
    args = parser.parse_args()

    main(args)
    
