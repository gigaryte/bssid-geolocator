#!/usr/bin/env python3
import logging
import argparse
import requests
import bssid_pb2
import simplekml
import logging
from urllib3.exceptions import InsecureRequestWarning

logging.basicConfig(level=logging.INFO)

#suppress certificate warnings for hitting Apple's location services API
#endpoint
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)

def geolocateApple(bssid):
    '''
    @brief: Attempts to geolocate a BSSID using the Apple location services API
    @param: bssid: the BSSID to attempt to geolocate
    @returns: list of (bssid, lat,lon, channel, horizontal_accuray) tuples

    @notes: much of this code borrowed from iSniff-GPS, who borrowed it from:

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
        #Need to normalize each MAC byte because the string representation will
        #strip out leading 0s for some reason. So for e.g., need to turn 
        # 0:11:22:33:44:55
        # into 00:11:22:33:44:55
        
        #BSSID
        paddedBSSID = ":".join("0" + x if len(x) == 1 else x for x in
                wifi.bssid.split(":"))
        #latitude 
        lat = wifi.location.lat * pow(10,-8) 
        #longitude
        lon = wifi.location.lon * pow(10,-8)
        #wi-fi channel
        channel = wifi.channel
        #horizontal accuracy (m)
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

def get_bssids_from_file(fname):
    '''
    @brief: Reads in a file of BSSIDs and returns them as a list
    @param: fname: the filename to read
    @returns: list of BSSIDs
    '''

    bssids = set()

    with open(fname, 'r') as f:
        for line in f:
            bssids.add(line.strip())

    return bssids

def main(args):

    # Single BSSID mode
    if args.bssid:
        #Single bssid geolocation requested
        locations = geolocateApple(args.bssid)
    # Batch mode
    elif args.infile:
        bssids = get_bssids_from_file(args.infile)

        locations = set()
        # Iterate the bssids
        for bssid in bssids:
            bssid_locations = geolocateApple(bssid)
            # Iterate the returned locations
            for location in bssid_locations:
                locations.add(location)
    if args.kml:
        writeKML(locations, args.kml)
    elif args.outfile:
        with open(args.outfile, 'w') as f:
            for location in locations:
                f.write(f"{'\t'.join([str(x) for x in location])}\n")
    else:
        for location in locations:
            print(f"{' '.join([str(x) for x in location])}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-b", "--bssid", help="Single BSSID to geo")
    parser.add_argument("-f", "--infile", help="File of BSSIDs to geo")
    parser.add_argument("-k", "--kml", help="Output KML filename")
    parser.add_argument("-o", "--outfile", help="Write output to TSV file")
    args = parser.parse_args()

    main(args)
    
