# -*- encoding: utf8 -*-
# from __future__ import unicode_strings
import requests
import json
from datetime import datetime
import io
import base64
import hashlib
import random
import struct
import logging
import time

from Crypto.Cipher import AES
from calendar import timegm

fotocasa_log = logging.getLogger(__name__)

def generate_imei(rnd=None):
    def luhn_digit(partial_imei):
        # https://en.wikipedia.org/wiki/Luhn_algorithm
        rpimei = [int(i) for i in partial_imei[::-1]]
        vals = [(i * 2) - (9 * ((i * 2)//10)) for i in range(10)]
        digit = sum([vals[i] for i in rpimei[::2]])
        digit += sum(i for i in rpimei[1::2])
        digit = (digit * 9) % 10
        return digit
    reporting_body_ids = [ ('01','USA'),
                           ('33','France'),
                           ('35','UK'),
                           ('44','UK'),
                           ('45','Denmark'),
                           ('49','Germany'),
                           ('50','Germany'),
                           ('51','Germany'),
                           ('52','Germany'),
                           ('53','Germany'),
                           ('86','China'),
                           ('91','India'),
                           ('98','UK'),
                         ]
    if rnd is None:
        rnd = random.Random()
        rnd.seed()
    head = rnd.choice(reporting_body_ids)
    # Real TAC (head + manufacturer) can be obtained from a database
    # http://tacdb.osmocom.org/
    # but I'm sure we do not need this here ;)
    device = "".join([str(rnd.randrange(10)) for i in range(6)])
    serial_number = "".join([str(rnd.randrange(10)) for i in range(6)])
    partial_imei = str(head[0]) + str(device) + str(serial_number)
    imei = partial_imei + str(luhn_digit(partial_imei))
    return imei


class Encryption(object):
    def __init__(self, key='ftcipanuntis2009'):
        self.key = hashlib.md5(key.encode('utf-8')).digest()
        # self.initialization_vector = buffer(bytearray(16))
        b = io.BytesIO(bytearray(16))
        self.initialization_vector = b.getbuffer()
        self.initialization_vector = bytes(bytearray(16))
        self.cbc_block_size = 16

    def _pkcs_7(self, message, blocksize):
        padd_byte = blocksize - (len(message) % blocksize)
        padding = struct.pack("{}B".format(padd_byte), *[padd_byte]*padd_byte)
        padded_message = message + padding
        return padded_message

    def encrypt(self, message):
        message = message.encode('utf-8')
        if len(message) % self.cbc_block_size != 0:
            message = self._pkcs_7(message, self.cbc_block_size)
        aes_crypt = AES.new(self.key, AES.MODE_CBC, self.initialization_vector)
        res = aes_crypt.encrypt(message)
        return res

    def decrypt(self, message):
        aes_crypt = AES.new(self.key, AES.MODE_CBC, self.initialization_vector)
        message = aes_crypt.decrypt(buffer(message))
        return message

    def encrypt_ftcws(self, message):
        padded_message = self._pkcs_7(message, self.cbc_block_size)
        aes_crypt = AES.new(self.key, AES.MODE_CBC, self.initialization_vector)
        res = aes_crypt.encrypt(message)
        return res

    def encrypt_to_hex(self, message):
        enc_message = self.encrypt(message)
        hex_message = ''.join('{:02x}'.format(x) for x in bytearray(enc_message))
        return hex_message

    def decrypt_from_hex(self, message):
        message = bytearray.fromhex(message)
        return self.decrypt(message)

    def encrypt_to_b64(self, message):
        enc_message = self.encrypt(message)
        b64_enc_message = ''.join('{:02x}'.format(x) for x in bytearray(enc_message))
        return b64_enc_message

    def decrypt_from_b64(self, message):
        decoded_b64 = base64.b64decode(message)
        return self.decrypt(str(decoded_b64))


def signature(imei=None, log=fotocasa_log):
    """
        The signature is composed of an IMEI number:
        https://en.wikipedia.org/wiki/International_Mobile_Equipment_Identity
        luckily python as a library to check a valid IMEI:
        https://arthurdejong.org/python-stdnum/

        and the milliseconds since 1970
        str(timegm()) + str(datetime.microsecond // 1000)
    """
    if imei is None:
        imei_gen = ImeiGen()
        imei = imei_gen.random_imei()
    if len(imei) != 15:
        log.warning('Len IMEI != 15 : %s', str(imei))
        raise ValueError('Imei should be 15 digits long')
    now = datetime.now()
    str_timestamp = str(timegm(now.timetuple())) + '{:03d}'.format(now.microsecond // 1000)
    to_sign = imei + str_timestamp
    if len(to_sign) != 28:
        log.warning('Len to sign != 28 : %s', str(to_sign))
        raise ValueError('To sign field should be 28 digits long')
    enc = Encryption()
    return enc.encrypt_to_hex(to_sign)


class BaseFilterRequestModel(object):
    def __init__(self, estate_type, offer_type):
        self.offerTypeId = offer_type
        self.categoryTypeId = estate_type[0]
        self.purchaseTypeId = estate_type[1]
        self.bathrooms = "0"
        self.conservationStates = ""
        self.extras = ""
        self.languageId = "3"
        self.latitude = ""
        self.locations = ""
        self.longitude = ""
        self.olapOriginId = "109" # WTF ?
        self.page = "1"
        self.pageSize = "36"
        self.periodicityIds = "0"
        self.platformId = "4"
        self.portalId = "49"
        self.priceFrom = "0"
        self.priceTo = "0"
        self.roomsFrom = "0"
        self.roomsTo = "0"
        self.signature = ""
        self.subcategoryTypes = ""
        self.surfaceFrom = "0"
        self.surfaceTo = "0"
        self.text = ""


class FilterRequestModel(BaseFilterRequestModel):
    def __init__(self, estate_type, offer_type):
        super(self.__class__, self).__init__(estate_type, offer_type)
        self.clientId = '0'
        self.sort = '0'


class RadialFilterRequestModel(BaseFilterRequestModel):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.radius = '2000'
        self.zoom = 16


class MapFilterRequestModel(BaseFilterRequestModel):
    """
        disableClustering = True, seems to disable additional information
            (only Id, and coordinates)
    """
    def __init__(self, estate_type=None, offer_type=None):
        super(self.__class__, self).__init__(estate_type, offer_type)
        self.disableClustering = "false"
        self.mapBoundingBox = ""
        self.polygon = ""
        self.sort = "0"
        self.zoom = 16

    def set_bounding_box(self, lat_0, lon_0, lat_1, lon_1):
        """
            mapBoundingBox coordinates are swapped (uses lon,lat pairs
            instead of lat, lon), and are a closed list of coordinates
            (start point and end point must be the same).
        """
        template = ';'.join(["{},{}"]*5)
        self.mapBoundingBox = template.format(lon_0, lat_0,
                                              lon_1, lat_0,
                                              lon_1, lat_1,
                                              lon_0, lat_1,
                                              lon_0, lat_0)
        self.latitude = str( (lat_0 + lat_1) / 2.0)
        # TODO, be careful at near the 'earth seam', were 180.0 joins -180.0
        self.longitude = str( (lon_0 + lon_1) / 2.0)


class GetLocationSuggestionsRequestModel(object):
    def __init__(self):
        self.categoryTypeId = "2"
        self.languageId = "3"
        self.maxItems = "10"
        self.offerTypeId = "3"
        self.purchaseTypeId = "2"
        self.signature = ""
        self.subcategoryTypes = "0"
        self.text = ""

class GetPropertyRequestModel(object):
    def __init__(self, property_id):
        self.languageId = 3
        self.transactionTypeId = 1
        self.periodicityId = 0
        self.propertyId = property_id
        self.longitude = 0.0
        self.latitude = 0.0

class FotocasaMapSearchEndpoints(object):
    def __init__(self):
        pass

    def bounding_box_search(self):
        endpoint = "/BoundingBoxSearchV2"

    def polygonal_search(self):
        endpoint = "/PolygonalSearch"

    def polygon_get_convex_hull(self):
        endpoint = "/PolygonGetConvexHull"


class FotocasaData(object):
    def __init__(self, json_dict, log=fotocasa_log):
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


class FotocasaDetailsResult(FotocasaData):
    required = [ ]
    optional = ["AdvertiserData",
                "AgencyLogo",
                "AgencyName",
                "AgencyReference",
                "BuildingStatus",
                "CategoryId",
                "Characteristics",
                "ClientId",
                "Contact",
                "DataLayer",
                "Description",
                "DiffPrice",
                "Distance",
                "EnergyCertificateId",
                "ExternalUrl",
                "ExtraList",
                "ExtraListDescription",
                "Floor",
                "HidePrice",
                "Id",
                "IsDevelopment",
                "IsFavorite",
                "IsProfessional",
                "LocationLevel1",
                "LocationLevel2",
                "LocationLevel3",
                "LocationLevel4",
                "Locations",
                "MainPhoto",
                "MarketerName",
                "MediaList",
                "NBathrooms",
                "NRooms",
                "OfferTypeId",
                "OriginId",
                "OriginalPrice",
                "ParametersRealMedia",
                "PaymentPeriodicityId",
                "PortalId",
                "Price",
                "PriceDescription",
                "ProductList",
                "PromoterName",
                "PromotionId",
                "PromotionName",
                "RelOfferTypeId",
                "RelOfferTypePrice",
                "ShowBankimia",
                "ShowCounterOffer",
                "ShowPoi",
                "Street",
                "SubTitleDescription",
                "SubcategoryId",
                "Surface",
                "Terrain",
                "Title",
                "TitleDescription",
                "TouristOfficeCode",
                "VideoList",
                "X",
                "Y",
                "ZipCode",
                ]



class FotocasaPropertyResult(FotocasaData):
    required = ['Id',
                'PriceDescription',
                'X',
                'Y',
                'Surface',
                'Bathrooms',
                'OfferTypeId',
                'ListDate',
                'LocationDescription',
                'NRooms',
                'PromotionId',
                'IsDevelopment',
                'TitleDescription',
                ]

    optional = ['Phone',
                'Photo',
                'PhotoSmall',
                'PhotoLarge',
                'PhotoMedium',
                'MediaList',
                'SubTitleDescription',
                'ProductList',
                'Distance',
                'PeriodicityId',
                'ShowPoi',
                'Comments',
               ]

    def __init__(self, json_dict, log=fotocasa_log):
        super(FotocasaPropertyResult, self).__init__(json_dict, log)


class FotocasaMetaDataResult(FotocasaData):
    int_fields = ['language_id',
                   'country_id',
                   'region_level1_id',
                   'region_level2_id',
                   'county_id',
                   'city_zone_id',
                   'city_id',
                   'locality_id',
                   'district_id',
                   'neighbourhood_id',
                   'price_min',
                   'price_max',
                   'mts2_min',
                   'mts2_max',
                   'bathrooms_min',
                   'rooms_min',
                   'rooms_max',
                   'transaction_id',
                   'property_id',
                   'property_sub_id',
                   'search_results_position',
                   'search_results_number']
    str_fields = ['transaction',
                  'property',
                 ]
    def __init__(self, url_encoded_data, log=fotocasa_log):
        params = url_encoded_data.split('&')
        for ifk in self.int_fields:
            setattr(self, ifk, 0)
        for sfk in self.str_fields:
            setattr(self, sfk, '')
        for kv_pair in params:
            try:
                pk, pv = kv_pair.split('=')
                if pk in self.int_fields:
                    setattr(self, pk, int(pv))
                if pk in self.str_fields:
                    setattr(self, pk, pv)
            except Exception as ex:
                log.exception('Error parsing METADATA: %s', str(url_encoded_data))


class FotocasaSearchResult(FotocasaData):

    def __init__(self, json_dict, log=fotocasa_log):
        self.properties = []
        self.metadata = None
        if json_dict is None:
            return
        if 'd' not in json_dict:
            return
        try:
            j_data = json_dict['d']
            self.metadata = FotocasaMetaDataResult(j_data['DataLayer'], log=log)
            if 'Properties' in j_data:
                for prop_result in j_data['Properties']:
                    fc_res = FotocasaPropertyResult(prop_result, log=log)
                    self.properties.append(fc_res)
        except Exception as ex:
            log.exception('Error parsing result %s', str(json_dict))


class FotocasaAPI(object):
    # The tuples correspond to the (categoryTypeId, purchaseTypeId)
    HOME = ('2', '2')
    NEW_HOME = ('2', '1')
    GARAGE = ('3', '2')
    LAND = ('4', '1')            # No RENT applies
    COMERCIAL = ('5', '1')
    OFFICE = ('6', '1')
    STORAGE_ROOM = ('7', '1')
    # BEDROOM = '' <- this would be the combination of HOMES + OFFER_SHARE
    # BUILDING = '' <- ?

    OFFER_RENT = "3"
    OFFER_BUY = "1"
    OFFER_TRANSFER = "4" # Only for COMMERCIAL (premises)
    OFFER_SHARE = "5"    # Only for HOMES wit purchaseTypeId = 1
    OFFER_HOLIDAY_RENTAL = "8"
    OFFER_WITH_PURCHASE_OPTION = "7"

    # v3 urls
    LOCAL = "http://afe0805531.sp.asm-corp:55763/mobile/api/v3.asmx"
    WIL = "http://afe0800705.sp.asm-corp:55763/mobile/api/v3.asmx"
    RAUL = "http://afe0801179.sp.asm-corp:8001/mobile/api/v3.asmx"
    DEV = "http://ws.dev.fotocasa.es/mobile/api/v3.asmx"
    PRE = "http://prews.fotocasa.es/mobile/api/v3.asmx"
    PRE2 = "https://prews2.fotocasa.es/mobile/api/v3.asmx"
    INTEGRA = "http://ws.integra.fotocasa.es/mobile/api/v3.asmx"
    CALABASH = "http://prews.fotocasa.es/mobile/api/v3.asmx"
    PRO = "https://ws.fotocasa.es/mobile/api/v3.asmx"

    handler_LOCAL = "http://172.30.7.223:55763/mobile/api"
    handler_WIL = "http://afe0800705.sp.asm-corp:55763/mobile/api"
    handler_RAUL = "http://afe0801179.sp.asm-corp:8001/mobile/api"
    handler_DEV = "http://ws.dev.fotocasa.es/mobile/api"
    handler_PRE = "http://prews.fotocasa.es/mobile/api"
    handler_PRE2 = "https://prews2.fotocasa.es/mobile/api"
    handler_INTEGRA = "http://ws.integra.fotocasa.es/mobile/api"
    handler_CALABASH = "http://prews.fotocasa.es/mobile/api"
    handler_PRO = "https://ws.fotocasa.es/mobile/api"

    def __init__(self, imei, estate_type=None, offer_type=None, config=None,
                 log=fotocasa_log, page_size=200, req_timeout=5.0):
        self.log = log
        self.page_size = page_size
        self.last_req_time = 0.0
        self.req_timeout = req_timeout
        self.estate_type = estate_type
        if not self.estate_type:
            self.estate_type = self.HOME
        self.offer_type = offer_type
        if not self.offer_type:
            self.offer_type = self.OFFER_RENT
        self.imei = imei
        if not config:
            config = 'PRO'
        else:
            config = config.upper()
        if hasattr(self, config):
            self.url = getattr(self, config)
        else:
            self.url = self.PRO
        if hasattr(self, 'handler_' + config):
            self.url_handler = getattr(self, 'handler_' + config)
        else:
            self.url_handler = self.handler_PRO

    def api_request(self, url, payload):
        headers = {
            "User-Agent" : "AndroidApp/5.63 (6.0.1/23; Samsung; Samsung_S8; 3.10.48-g1abae1a; 4.0.0.04_20181125-1352)"
        }
        try:
            data_payload = json.dumps(payload)
            start_time = time.time()
            res = requests.post(url,
                                headers=headers,
                                json=payload,
                                timeout=self.req_timeout)
            end_time = time.time()
            self.last_req_time = end_time - start_time
            json_response = json.loads(res.text)
        except requests.ConnectionError as conn_err:
            self.log.exception('Connection Error url:%s payload:%s', str(url), str(payload))
            return None
        except requests.Timeout as tout:
            self.log.exception('Request timeout url:%s payload:%s', str(url), str(payload))
            return None
        except requests.exceptions.RequestException as req_ex:
            self.log.exception('Request exception url:%s payload:%s', str(url), str(payload))
            return None
        except json.decoder.JSONDecodeError as jde:
            self.log.exception('Error decoding json: %s', str(res.text))
            return None
        except Exception as es:
            self.log.exception('Unexpected exception')
            return None
        return json_response

    def search_by_bounding_box(self, lat_0, lon_0, lat_1, lon_1, page_num=1):
        mfrm = MapFilterRequestModel(estate_type=self.estate_type,
                                     offer_type=self.offer_type)
        mfrm.set_bounding_box(lat_0, lon_0, lat_1, lon_1)
        mfrm.pageSize = self.page_size
        if page_num < 1:
            page_num = 1
        self.log.info('search_by_bounding_box page:%-3d  coords:(%f, %f - %f, %f)',
                  page_num, lat_0, lon_0, lat_1, lon_1)
        mfrm.page = page_num
        mfrm.signature = signature(imei=self.imei)
        return self.api_request(self.url + "/BoundingBoxSearchV2", vars(mfrm))

    def search_by_coordinates(self, lat, lon):
        endpoint = self.url + '/Search'
        frm = FilterRequestModel(estate_type=self.estate_type,
                                 offer_type=self.offer_type)
        frm.pageSize = self.page_size
        frm.latitude = lat
        frm.longitude = lon
        frm.sort = '1'
        frm.signature = signature(imei=self.imei)
        self.log.info('search_by_coordinates page:  1 coords:(%f, %f)', lat, lon)
        return self.api_request(endpoint, vars(frm))

    def search_by_location(self, location_text):
        locations = self.get_locations(location_text)
        if 'd' not in locations or 'Suggest' not in locations['d']:
            return None
        if len(locations['d']['Suggest']) == 0:
            return None
        location = locations['d']['Suggest'][0]
        location_codes = [location['LocationLevel' + str(i)] for i in range(1,6)]
        lat = location['Y']
        lon = location['X']
        return self.search_by_location_codes(location_codes, lat, lon)

    def search_by_location_codes(self, location_codes, lat, lon):
        endpoint = self.url + '/Search'
        frm = FilterRequestModel(estate_type=self.estate_type,
                                 offer_type=self.offer_type)
        frm.locations = ','.join(location_codes)
        frm.pageSize = self.page_size
        frm.latitude = lat
        frm.longitude = lon
        frm.signature = signature(imei=self.imei)
        return self.api_request(endpoint, vars(frm))

    def get_locations(self, location_text):
        endpoint = self.url + '/GetSuggest'
        glsrm = GetLocationSuggestionsRequestModel()
        glsrm.text = location_text
        glsrm.signature = signature(imei=self.imei)
        return self.api_request(endpoint, vars(glsrm))
