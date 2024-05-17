# bssid-geolocator

To install and manage dependencies, I use `virutalenv`:

```bash
virtualenv -p python3 .
source bin/activate
pip install -r requirements.txt
```

`bssid-geolocator` is very simple. It takes one BSSID as an argument, and
produces all the geolocations to stdout. It can also write KML.


## Examples

```bash
./bssid-geolocator.py 00:11:22:33:44:55 
```

Produces output like:

```
<unix ts> <bssid> <lat,lon> <channel> <horizonal accuracy>
```

You can also write KML with `-k`:

```bash
./bssid-geolocator.py -k output.kml 00:11:22:33:44:55 
```

There's also a help menu, if you forget all of this:

```bash
./bssid-geolocator.py -h
```
