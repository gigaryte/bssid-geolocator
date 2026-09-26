#!/usr/bin/env python3
import logging
import argparse
import requests
import bssid_pb2
import simplekml
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from urllib3.exceptions import InsecureRequestWarning

# Suppress certificate warnings for hitting Apple's location services API
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Custom logger
logger = logging.getLogger("bssid-geolocator")
logging.basicConfig(level=logging.ERROR)

# WLOC endpoint. Apple runs a separate service for mainland China;
# --cn points at it instead of the default.
WLOC_HOST = "gs-loc.apple.com"
WLOC_HOST_CN = "gs-loc-cn.apple.com"

# Thread-local requests.Session — one per worker for connection reuse,
# with retries disabled so we fail fast instead of hanging.
_thread_local = threading.local()

def _get_session():
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=0)
        s.mount("https://", a)
        _thread_local.session = s
    return _thread_local.session


def geolocateApple(bssid):
    session = _get_session()

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

    r = session.post(f'https://{WLOC_HOST}/clls/wloc', headers=headers,
                     data=data, verify=False, timeout=(5, 10))

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


def filter_locations(locations, queried_bssids):
    """Keep only locations whose BSSID was in the original query set."""
    return [loc for loc in locations if loc[0] in queried_bssids]


def get_bssids_from_file(fname):
    bssids = set()
    with open(fname, 'r') as f:
        for line in f:
            bssids.add(line.strip())
    return bssids


class ProgressTracker:
    """Thread-safe progress bar written to stderr."""

    def __init__(self, total, bar_width=40):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.skipped = 0
        self.bar_width = bar_width
        self.lock = threading.Lock()
        self.start_time = time.monotonic()
        self._render()

    def _render(self):
        elapsed = time.monotonic() - self.start_time
        done = self.completed + self.failed + self.skipped
        remaining = self.total - done
        pct = done / self.total if self.total else 1
        filled = int(self.bar_width * pct)
        bar = "█" * filled + "░" * (self.bar_width - filled)

        if done > 0 and done < self.total:
            rate = done / elapsed
            eta = remaining / rate
            eta_str = f"ETA {eta:.0f}s"
        elif done >= self.total:
            eta_str = f"done in {elapsed:.1f}s"
        else:
            eta_str = "..."

        tags = []
        if self.failed:
            tags.append(f"{self.failed} err")
        if self.skipped:
            tags.append(f"{self.skipped} skip")
        tag_str = f" ({', '.join(tags)})" if tags else ""
        line = f"\r  [{bar}] {done}/{self.total}{tag_str} — {eta_str}"
        sys.stderr.write(f"{line:<80}")
        sys.stderr.flush()

    def tick(self, success=True):
        with self.lock:
            if success:
                self.completed += 1
            else:
                self.failed += 1
            self._render()

    def skip(self, n=1):
        with self.lock:
            self.skipped += n
            self._render()

    def finish(self):
        sys.stderr.write("\n")
        sys.stderr.flush()


class StreamingWriter:
    """Thread-safe incremental output writer."""

    def __init__(self, args, queried_bssids):
        self.args = args
        self.queried_bssids = queried_bssids
        self.lock = threading.Lock()

        # KML needs to accumulate then save once at the end
        if args.kml:
            self.kml = simplekml.Kml()
        else:
            self.kml = None

        # JSON must buffer (need valid array at the end)
        if args.json:
            self.json_buf = []
        else:
            self.json_buf = None

        # Open TSV file handle if needed
        if args.outfile:
            self.outfh = open(args.outfile, 'w')
        else:
            self.outfh = None

        # Track seen location tuples for dedup across responses
        self.seen = set()
        # Track all BSSIDs we've seen locations for (used to skip requests)
        self.seen_bssids = set()

    def write(self, locations):
        """Write a batch of locations from one request.
        Returns the set of BSSIDs that appeared in these results."""
        if self.args.ignore:
            locations = filter_locations(locations, self.queried_bssids)

        new_bssids = set()
        with self.lock:
            for loc in locations:
                bssid = loc[0]
                new_bssids.add(bssid)
                self.seen_bssids.add(bssid)

                if loc in self.seen:
                    continue
                self.seen.add(loc)

                _, ll, channel, hacc = loc
                lat = float(ll.split(',')[0])
                lon = float(ll.split(',')[1])

                if self.kml is not None:
                    if not (lat == -180 and lon == -180):
                        self.kml.newpoint(name=bssid, description=bssid,
                                          coords=[(lon, lat)])

                elif self.json_buf is not None:
                    self.json_buf.append({
                        "bssid": bssid,
                        "lat": lat,
                        "lon": lon,
                        "channel": channel,
                        "accuracy": hacc,
                    })

                elif self.outfh is not None:
                    self.outfh.write('\t'.join(str(x) for x in loc) + '\n')
                    self.outfh.flush()

                else:
                    print(f"{' '.join(str(x) for x in loc)}", flush=True)

        return new_bssids

    def already_seen(self, bssid):
        """Check if we already have a location for this BSSID."""
        with self.lock:
            return bssid in self.seen_bssids

    def finalize(self):
        """Flush any buffered output."""
        if self.kml is not None:
            self.kml.save(self.args.kml)
            sys.stderr.write(f"KML saved to {self.args.kml}\n")

        if self.json_buf is not None:
            print(json.dumps(self.json_buf, indent=2))

        if self.outfh is not None:
            self.outfh.close()


def main(args):
    if args.bssid:
        bssids = {args.bssid}
    elif args.infile:
        bssids = get_bssids_from_file(args.infile)
    else:
        logger.error("Neither a BSSID nor infile were provided")
        exit(-1)

    writer = StreamingWriter(args, bssids)
    progress = ProgressTracker(len(bssids))

    # Convert to a list so we can iterate and check seen_bssids before submitting.
    # We feed work in batches rather than all at once so that BSSIDs returned
    # as bonus results from earlier requests can be skipped.
    pending = list(bssids)

    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        idx = 0          # next index into pending to consider
        in_flight = {}   # future -> bssid

        while idx < len(pending) or in_flight:
            # Fill up to N in-flight slots
            while idx < len(pending) and len(in_flight) < args.threads:
                bssid = pending[idx]
                idx += 1
                if writer.already_seen(bssid):
                    progress.skip()
                    continue
                fut = pool.submit(geolocateApple, bssid)
                in_flight[fut] = bssid

            if not in_flight:
                break

            # Wait for at least one to finish
            done_futs, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for fut in done_futs:
                bssid = in_flight.pop(fut)
                try:
                    locations = fut.result()
                    writer.write(locations)
                    progress.tick(success=True)
                except Exception:
                    logger.exception(f"Failed to geolocate {bssid}")
                    progress.tick(success=False)

    progress.finish()
    writer.finalize()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bssid", help="Single BSSID to geo")
    parser.add_argument("-f", "--infile", help="File of BSSIDs to geo")
    parser.add_argument("-k", "--kml", help="Output KML filename")
    parser.add_argument("-I", "--ignore", action="store_true", help="Ignore extra 400")
    parser.add_argument("-o", "--outfile", help="Write output to TSV file")
    parser.add_argument("--json", action="store_true", help="Print output as JSON")
    parser.add_argument("--cn", action="store_true",
                        help="Query Apple's China WLOC endpoint (gs-loc-cn.apple.com)")
    parser.add_argument("-N", "--threads", type=int, default=10,
                        help="Number of concurrent request threads (default: 10)")
    args = parser.parse_args()

    if args.cn:
        WLOC_HOST = WLOC_HOST_CN

    main(args)
