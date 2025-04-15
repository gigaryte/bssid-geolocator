# bssid-geolocator

To install and manage dependencies, I use `virtualenv`:

```bash
virtualenv -p python3 .
source bin/activate
pip install -r requirements.txt
```

To run this on Nix, do:
```
nix-shell
[nix-shell:~/Downloads/bssid-geolocator]$ ./bssid-geolocator.py --bssid 00:11:22:33:44:55
INFO:root:Geolocating bssid 00:11:22:33:44:55
00:11:22:33:44:55 -180.0,-180.0 0 -1
```

`bssid-geolocator` is very simple. It takes one BSSID as an argument, and
produces all the geolocations to stdout. It can also write KML.


## Examples

```bash
./bssid-geolocator.py -b 00:11:22:33:44:55
```

Produces output like:

```
<bssid> <lat,lon> <channel> <horizonal accuracy>
```

You can also geolocate several BSSIDs from a file with `-f`:

```bash
./bssid-geolocator.py -f file-o-bssids.txt
```

You can write the output to a file with `-o`, which produces a tsv for easy
`cut`ing:

```bash
./bssid-geolocator.py -f file-o-bssids.txt -o geos.tsv
```

You can also write KML with `-k`:

```bash
./bssid-geolocator.py -k output.kml -b 00:11:22:33:44:55
```

You can output results in JSON format with `--json` (useful for scripting and integration):

```
./bssid-geolocator.py -b 00:11:22:33:44:55 --json

```

Sample output:

```
[
  {
    "bssid": "00:11:22:33:44:55",
    "lat": 14.4463227,
    "lon": 26.0369489,
    "channel": 3,
    "accuracy": 24
  }
]

```

> ℹ️ The `--json` flag disables all console logs for clean machine-readable output.

There's also a help menu, if you forget all of this:

```bash
./bssid-geolocator.py -h
```
