# -*- encoding: utf8 -*-
# from __future__ import unicode_strings
import requests
import json
from datetime import datetime
import io
import os
import logging
import time
import random
import hashlib

"""
About Images:
When looking for images, take into account that:
- search api (does not have watermarked image, but is a little bit smaller):
    https://img3.idealista.com/blur/WEB_LISTING-M/0/id.pro.es.image.master/dd/d8/59/126659322.jpg
- detail (comes with watermarked image, a little bit bigger):
    https://img3.idealista.com/blur/WEB_DETAIL-L-L/0/id.pro.es.image.master/dd/d8/59/126659322.jpg
- multimedia (exactly the same url than detail):
    https://img3.idealista.com/blur/WEB_DETAIL-L-L/0/id.pro.es.image.master/dd/d8/59/126659322.jpg

TODO: look if we can request bigger images to the search api
"""

idealista_log = logging.getLogger(__name__)

class IdealistaData(object):
    def __init__(self, json_dict, log=idealista_log):
        for field in self.required:
            if field in json_dict:
                setattr(self, field, json_dict[field])
            else:
                log.error('Missing required field %s', str(field))
                raise ValueError('missing required field {}'.format(field))
        for field in self.optional:
            if field in json_dict:
                setattr(self, field, json_dict[field])
            else:
                setattr(self, field, None)


class IdealistaImage(IdealistaData):
    required = ['url', ]
    optional = ['multimediaTag',]

    def __init__(self, json_dict):
        super(IdealistaImage, self).__init__(json_dict)


class IdealistaMultimedia(object):
    def __init__(self, json_data):
        self.images = []
        if 'images' in json_data:
            for img in json_data['images']:
                i_image = IdealistaImage(img)
                self.images.append(i_image)


class IdealistaPhoneInfo(IdealistaData):
    required = []
    optional = [
        "phoneNumberForMobileDialing",
        "formattedPhone",
        "nationalNumber",
        "phoneNumber",
    ]


class IdealistaContactInfo(IdealistaData):
    required = []
    optional = [
            "inVirtualMicrosite",
            "contactMethod",
            "contactName",
            "userType",
        ]

    def __init__(self, json_dict):
        super(IdealistaContactInfo, self).__init__(json_dict)
        if 'phone1' in json_dict:
            self.phone1 = IdealistaPhoneInfo(json_dict['phone1'])
        else:
            self.phone1 = None


class IdealistaDetailedType(IdealistaData):
    required = []
    optional = ['typology', 'subTypology']
    def __init__(self, json_dict):
        super(IdealistaDetailedType, self).__init__(json_dict)


class IdealistaSearchResultElement(IdealistaData):
    required = [
        "propertyCode",
        "propertyType",
        'url',
        "latitude",
        "longitude",
        'address',
        "country",
        "province",
        "municipality",
        "price",
        "operation",
        "numPhotos",
        "hasVideo",
    ]
    optional = [
        "floor",
        "bathrooms",
        "exterior",
        "hasLift",
        "size",
        "distance",
        "status",
        "topHighlight",
        "urgentVisualHighlight",
        "visualHighlight",
        "preferenceHighlight",
        "showAddress",
        "rooms",
        "priceByArea",
        "newDevelopment",
        "newProperty",
        "favourite",
        "firstActivationDate",
        "externalReference",
        "neighborhood",
        "district",
        'thumbnail',
    ]

    def __init__(self, json_dict):
        super(IdealistaSearchResultElement, self).__init__(json_dict)
        self.contactInfo = None
        self.multimedia = None
        self.suggestedTexts = None
        self.detailedType = None
        if 'contactInfo' in json_dict:
            self.contactInfo = IdealistaContactInfo(json_dict['contactInfo'])
        else:
            self.contactInfo = None
        if 'multimedia' in json_dict:
            self.multimedia = IdealistaMultimedia(json_dict['multimedia'])
        else:
            self.multimedia = None
        if 'suggestedTexts' in json_dict:
            self.suggestedTexts = json_dict['suggestedTexts']
        else:
            self.suggestedTexts = None
        if 'detailedType' in json_dict:
            self.detailedType = IdealistaDetailedType(json_dict['detailedType'])
        else:
            self.detailedType = None


class IdealistaSearchResults(IdealistaData):
    required = [
        "totalPages",
        ]
    optional = [
        "total",
        "actualPage",
        "upperRangePosition",
        ]

    def __init__(self, json_dict):
        super(self.__class__, self).__init__(json_dict)
        self.element_list = []
        if "elementList" in json_dict:
            for el in json_dict['elementList']:
                idealista_element = IdealistaSearchResultElement(el)
                self.element_list.append(idealista_element)


class IdealistaAPI(object):
    OPERATION_RENT = u"rent"
    OPERATION_SALE = u"sale"

    PROPERTY_HOMES = u"homes"
    PROPERTY_OFFICES = u"offices"
    PROPERTY_COMMERCIAL_PROPERTY = u"premises"
    PROPERTY_GARAGES = u"garages"
    PROPERTY_BUILDINGS = u"buildings"
    PROPERTY_STORAGE_ROOMS = u"storageRooms"
    PROPERTY_LANDS = u"lands"
    PROPERTY_BEDROOMS = u"bedrooms"

    URL_OAUTH_TOKEN = u"https://secure.idealista.com/api/oauth/token"
    URL_SEARCH = u"https://secure.idealista.com/api/3.5/es/search"
    URL_DETAIL = u"https://secure.idealista.com/api/3/es/detail/{property_id}"

    # TODO: implement the locations requests:
    # can get points of interest
    URL_LOCATIONS = u"https://secure.idealista.com/api/3/es/locations?coordinates=41.4389239%2C2.195738&showPois=true"
    URL_MAP_SEARCH = u"https://secure.idealista.com/api/3.5/es/map/search?t=14566605368570.7027966808362714&k=5b85c03c16bbb85d96e232b112ee85dc"

    def __init__(self, locale='en',
                       user_id='5b85c03c16bbb85d96e232b112ee85dc', # this is hardcoded in the app
                       property_type=u'homes',
                       operation=u'rent',
                       log=idealista_log,
                       page_size=50,
                       req_timeout=10.0):
        self.log = log
        self.locale = locale
        self.user_id = user_id
        self.property_type = property_type
        self.operation = operation
        self.lang = u"en"
        self.page_size = page_size
        self.last_req_time = 0.0
        self.req_timeout = req_timeout


        # # The Basic auth is always the same because uses the api key and the api
        # # secret, so it is always the same :/
        # self.api_key = "5b85c03c16bbb85d96e232b112ee85dc"
        # self.secret_key = 'idea:andr01d'
        # and combined results in this header:
        self.auth = 'Basic NWI4NWMwM2MxNmJiYjg1ZDk2ZTIzMmIxMTJlZTg1ZGM6aWRlYSUzQmFuZHIwMWQ='
        self.app_version = "7.3.7"
        # self.app_version = "8.0.12"

        self._create_terminal()

    def _create_terminal(self):
        user_agents = [
            'Dalvik/2.1.0 (Linux; U; Android 6.0.1; SM-G930F Build/MMB29K)',
            'Dalvik/2.1.0 (Linux; U; Android 6.0.1; Aquaris E5 Build/MMB29M)',
            'Dalvik/2.1.0 (Linux; U; Android 6.0; LG-H815 Build/MRA58k)',
            'Dalvik/2.1.0 (Linux; U; Android 7.0; Moto C Plus Build/NRD90M.03.040)',
            'Dalvik/2.1.0 (Linux; U; Android 7.1.1; XT1710-02 Build/NDSS26.118-23-11)',
        ]
        self.t_param = self._t_param()
        self.user_agent = random.choice(user_agents)
        self.app_version = "7.3.7"

    def authorize(self):
        oauth_token_url = self.URL_OAUTH_TOKEN
        self._create_terminal()
        self.android_device_identifier = hashlib.sha256(self.t_param.encode('utf-8')).hexdigest()[-16:]
        headers = {
            "User-Agent": self.user_agent, # "Dalvik/2.1.0 (Linux; U; Android 6.0.1; Aquaris E5 Build/MMB29M)",
            "app_version": self.app_version,
            "device_identifier" : self.android_device_identifier, # "93b2ea0cda87df5b",
            "Authorization" : self.auth,
            "country": 'es'
        }
        data_payload = {
            "grant_type": "client_credentials",
            "scope": "write",
        }
        try:
            res = requests.post(oauth_token_url,
                                headers=headers,
                                data=data_payload,
                                timeout=self.req_timeout)
            token_body = res.text
            return token_body
        except requests.ConnectionError as conn_err:
            self.log.exception('IDEALISTA Auth # Connection Error url:%s payload:%s',
                                str(url), str(payload))
            return None
        except requests.Timeout as tout:
            self.log.exception('IDEALISTA Auth # Request timeout url:%s payload:%s',
                                str(url), str(payload))
            return None
        except requests.exceptions.RequestException as req_ex:
            self.log.exception('IDEALISTA Auth # Request exception url:%s payload:%s',
                                str(url), str(payload))
            return None
        except Exception as es:
            self.log.exception('IDEALISTA Auth # Unexpected exception')
            return None

    def load_authorization(self, token_response):
        """ loads a previously acquired token from file """
        try:
            oauth_response = json.loads(token_response)
            self.access_token = oauth_response['access_token']
            return True
        except Exception as e:
            self.log.exception('Can not load access token')
            return False

    def _create_shape(self, lat_0, lon_0, lat_1, lon_1):
        # shape must end in the same number that it starts
        template = ';'.join(["{},{},0"]*5)
        self.mapBoundingBox = template.format(lon_0, lat_0,
                                              lon_1, lat_0,
                                              lon_1, lat_1,
                                              lon_0, lat_1,
                                              lon_0, lat_0)
        shape = { "type" : "MultiPolygon",
                  "coordinates" : [ [ [
                        [lon_0, lat_0, 0],
                        [lon_1, lat_0, 0],
                        [lon_1, lat_1, 0],
                        [lon_0, lat_1, 0],
                        [lon_0, lat_0, 0]
                    ] ] ]
                }
        return json.dumps(shape)

    def _token_auth(self):
        return "Bearer " + self.access_token

    def _common_headers(self, auth):
        headers = {
            "User-Agent": self.user_agent, # "Dalvik/2.1.0 (Linux; U; Android 6.0.1; Aquaris E5 Build/MMB29M)",
            "app_version": self.app_version,
            "device_identifier" : self.android_device_identifier, # "93b2ea0cda87df5b",
            "Authorization" : auth,
        }
        return headers

    def _t_param(self):
        # terminal_id param
        n = datetime.now()
        return str(n.timestamp() * 10000.0)

    def get_detail(self, property_id):
        url = self.DETAIL_URL.format(property_id=property_id)
        url_params = { 'language' : self.lang,
                       'k' : self.user_id,
                       't' : self.t_param, # self._t_param(),
                     }

    def search_by_bounding_box(self, lat_0, lon_0, lat_1, lon_1, page_num=1):
        url = self.URL_SEARCH
        shape = self._create_shape(lat_0, lon_0, lat_1, lon_1)
        url_params = {
                    'numPage' : page_num,
                    'k' : self.user_id,
                    't' : self.t_param, # self._t_param(),
                    }
        # TODO:
        # check if this kind of request works as expected:
        form_params = {
            u"shape": shape,
            u"propertyType": self.property_type,
            u"locale":       self.lang,
            u"maxItems":     0,
            u"numPage":      0,
            u"country":      "es",
            u"operation":    self.operation,
            u"distance":     0,
        }
        # it looks like this call is made to fetch the number of items in the bounding
        # box
        form_params = {
                u"shape":        shape,
                u"order":        u"distance",
                u"mPolygons":    u"[com.idealista.android.domain.model.polygon.Polygon@d58f746]",
                u"propertyType": self.property_type,
                u"locale":       self.locale,
                u"isPoi":        u"true",
                u"maxItems":     self.page_size,
                u"locationName": u"",
                u"numPage":      1,
                u"operation":    self.operation,
                u"distance":     2000,
                u"sort":         u"asc",
                u"height":       450,
                u"width":        600,
                u"gallery":      u"true",
                u"quality":      u"high",
                      }
        headers = self._common_headers(self._token_auth())
        try:
            start_time = time.time()
            res = requests.post(url, params=url_params, data=form_params,
                                headers=headers, timeout=self.req_timeout)
            end_time = time.time()
            self.last_req_time = end_time - start_time
        except requests.ConnectionError as conn_err:
            self.log.exception('IDEALISTA API # Connection Error url:%s payload:%s',
                                str(url), str(payload))
            return None
        except requests.Timeout as tout:
            self.log.exception('IDEALISTA API # Request timeout url:%s payload:%s',
                                str(url), str(payload))
            return None
        except requests.exceptions.RequestException as req_ex:
            self.log.exception('IDEALISTA API # Request exception url:%s payload:%s',
                                str(url), str(payload))
            return None
        except Exception as es:
            self.log.exception('IDEALISTA API # Unexpected exception')
            return None
        return res.text

    def search_by_location(self, location_name, save_to_file=None, page=1):
        url = self.URL_SEARCH
        url_params = {
                    'numPage' : page,
                    'k' : self.user_id,
                    't' : self._t_param(),
                    }
        form_params = {
                u"shape":        shape,
                u"order":        u"distance",
                u"mPolygons":    u"[com.idealista.android.domain.model.polygon.Polygon@d58f746]",
                u"propertyType": u"premises",
                u"locale":       self.locale,
                u"isPoi":        u"true",
                u"maxItems":     self.page_size,
                u"locationName": location_name,
                u"numPage":      1,
                u"operation":    self.operation,
                u"distance":     2000,
                u"sort":         u"asc",
                u"height":       450,
                u"width":        600,
                u"gallery":      u"true",
                u"quality":      u"high",
                      }
        headers = self._common_headers(self._token_auth())
        res = requests.post(url, params=url_params, data=form_params,
                            headers=headers)
        if save_to_file:
            output_file = '{}_{}'.format(save_to_file,
                                         datetime.now().strftime('%m%d_%H%M'))
            with io.open(output_file, 'w', encoding='utf-8') as of:
                of.write(res.text)
        return res.text


class IdealistaLocalStorage(object):
    def __init__(self, storage_dir=".", log=idealista_log):
        self.log = log
        self.storage_dir = storage_dir
        self.token_file = "oauth_token.json"

    def load_token(self):
        try:
            fullpath_file = os.path.join(self.storage_dir, self.token_file)
            with open(fullpath_file, 'r') as tsf:
                res = tsf.read()
            return res
        except Exception as e:
            return None

    def token_date(self):
        try:
            fullpath_file = os.path.join(self.storage_dir, self.token_file)
            fstat = os.stat(fullpath_file)
            dt = datetime.utcfromtimestamp(fstat.st_ctime)
            return dt
        except Exception as ex:
            return None

    def store_token(self, json_token_response):
        fullpath_file = os.path.join(self.storage_dir, self.token_file)
        with open(fullpath_file, 'w') as tsf:
            tsf.write(json_token_response)

    def load_stored_result(self, filename):
        fullpath_file = os.path.join(self.storage_dir, filename)
        try:
            with open(fullpath_file, 'r') as fo:
                res = fo.read()
            return res
        except Exception as e:
            self.log.exception('Can not load stored result')
            return None

    def store_result(self, filename, result):
        if not result:
            return
        fullpath_file = os.path.join(self.storage_dir, filename)
        with open(fullpath_file, 'w') as tsf:
            tsf.write(result)
