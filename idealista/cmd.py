""" Idealista command line requests

Usage:
    cmd.py bbox <min_lat> <min_lon> <max_lat> <max_lon> [<token_file>]
    cmd.py loc  <location_name> [<token_file>]
"""
import json
import time
from docopt import docopt
from pprint import pprint as _p
from idealista import IdealistaAPI, IdealistaSearchResults

if __name__ == '__main__':
    args = docopt(__doc__)
    _p(args)
    iapi = IdealistaAPI()
    token_file = args['<token_file>']
    if token_file:
        iapi.load_authorization(token_store_file=token_file)
    else:
        res = iapi.authorize()
        iapi.load_authorization(res)
    if args['loc']:
        location_name = args['<location_name>']
        res = iapi.search_by_location(location_name)
        _p(res)
    elif args['bbox']:
        lat_0 = float(args['<min_lat>'])
        lon_0 = float(args['<min_lon>'])
        lat_1 = float(args['<max_lat>'])
        lon_1 = float(args['<max_lon>'])
        res = iapi.search_by_bounding_box(lat_0, lon_0, lat_1, lon_1)
        _p(res)
