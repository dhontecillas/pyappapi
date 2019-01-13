""" Fotocasa command line requests

Usage:
    cmd.py bbox <min_lat> <min_lon> <max_lat> <max_lon>
    cmd.py loc  <location_name>
"""
import json
import time
from docopt import docopt
from pprint import pprint as _p
from fotocasa import FotocasaAPI, generate_imei

FAKE_IMEI = '536449977880378'

if __name__ == '__main__':
    args = docopt(__doc__)
    if args['loc']:
        location_name = args['<location_name>']
        fapi = FotocasaAPI(imei=FAKE_IMEI, config=None)
        res = fapi.search_by_location(location_name)
        _p(res)
    elif args['bbox']:
        lat_0 = float(args['<min_lat>'])
        lon_0 = float(args['<min_lon>'])
        lat_1 = float(args['<max_lat>'])
        lon_1 = float(args['<max_lon>'])
        fapi = FotocasaAPI(imei=FAKE_IMEI, config=None, page_size=72)
        res = fapi.search_by_bounding_box(lat_0, lon_0, lat_1, lon_1)
        print(json.dumps(res))
        print('results : {}'.format( len( res['d']['Properties'])))
