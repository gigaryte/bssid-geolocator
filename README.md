# bssid-geolocator

To install and manage dependencies, I use `virtualenv`:

```bash
virtualenv -p python3 .
source bin/activate
pip install -r requirements.txt
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

There's also a help menu, if you forget all of this:

```bash
./bssid-geolocator.py -h
```
