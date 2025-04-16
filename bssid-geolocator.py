#!/usr/bin/env python3
import logging
import argparse
import requests
import bssid_pb2
import simplekml
import json
from urllib3.exceptions import InsecureRequestWarning

# Suppress certificate warnings for hitting Apple's location services API
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Custom logger
logger = logging.getLogger("bssid-geolocator")
logging.basicConfig(level=logging.INFO)


def geolocateApple(bssid, silent=False):
    if not silent:
        logger.info(f"Geolocating bssid {bssid}")

    data_bssid = f"\x12\x13\n\x11{bssid}\x18\x00\x20\00"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        "Accept-Charset": "utf-8",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-us",
        'User-Agent': 'locationd/1753.17 CFNetwork/711.1.12 Darwin/14.0.0'
    }
    data = "\x00\x01\x00\x05en_US\x00\x13com.apple.locationd\x00\x0a" + \
           "8.1.12B411\x00\x00\x00\x01\x00\x00\x00" + \
           chr(len(data_bssid)) + data_bssid

    r = requests.post('https://gs-loc.apple.com/clls/wloc', headers=headers, data=data, verify=False)

    bssidResponse = bssid_pb2.WiFiLocation()
    bssidResponse.ParseFromString(r.content[10:])

    geos = []

    for wifi in bssidResponse.wifi:
        paddedBSSID = ":".join("0" + x if len(x) == 1 else x for x in wifi.bssid.split(":"))
        lat = wifi.location.lat * pow(10, -8)
        lon = wifi.location.lon * pow(10, -8)
        channel = wifi.channel
        hacc = wifi.location.hacc
        geos.append((paddedBSSID, f"{lat},{lon}", channel, hacc))

    return geos


def writeKML(locations, fname):
    kml = simplekml.Kml()

    for res in locations:
        bssid = res[0]
        ll = res[1]
        lat = float(ll.split(',')[0])
        lon = float(ll.split(',')[1])

        if lat == -180 and lon == -180:
            continue

        kml.newpoint(name=bssid, description=f"{bssid}", coords=[(lon, lat)])

    kml.save(fname)


def get_bssids_from_file(fname):
    bssids = set()
    with open(fname, 'r') as f:
        for line in f:
            bssids.add(line.strip())
    return bssids


def main(args):
    silent = args.json

    if args.bssid:
        locations = geolocateApple(args.bssid, silent=silent)
    elif args.infile:
        bssids = get_bssids_from_file(args.infile)
        locations = set()
        for bssid in bssids:
            bssid_locations = geolocateApple(bssid, silent=silent)
            for location in bssid_locations:
                locations.add(location)
    else:
        logger.error("Neither a BSSID nor infile were provided")
        exit(-1)

    if args.kml:
        writeKML(locations, args.kml)
    elif args.outfile:
        with open(args.outfile, 'w') as f:
            for location in locations:
                line = '\t'.join([str(x) for x in location])
                f.write(f"{line}\n")
    elif args.json:
        json_data = [
            {
                "bssid": loc[0],
                "lat": float(loc[1].split(',')[0]),
                "lon": float(loc[1].split(',')[1]),
                "channel": loc[2],
                "accuracy": loc[3]
            } for loc in locations
        ]
        print(json.dumps(json_data, indent=2))
    else:
        for location in locations:
            print(f"{' '.join([str(x) for x in location])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bssid", help="Single BSSID to geo")
    parser.add_argument("-f", "--infile", help="File of BSSIDs to geo")
    parser.add_argument("-k", "--kml", help="Output KML filename")
    parser.add_argument("-o", "--outfile", help="Write output to TSV file")
    parser.add_argument("--json", action="store_true", help="Print output as JSON")
    args = parser.parse_args()

    main(args)
