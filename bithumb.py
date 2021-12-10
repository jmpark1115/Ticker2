import time
import base64
import hmac, hashlib
import urllib.parse
import urllib.request
import requests

from decimal import Decimal as D
from decimal import getcontext

import logging
logger = logging.getLogger(__name__)

#Doc = 'https://apidocs.bithumb.com/docs/ticker'
API_URL = 'https://api.bithumb.com'

class Bithumb(object):
    def __init__(self, target, payment, key, secret):
        self.target = target.upper()
        self.payment = payment.upper()
        self.symbol = "{}_{}".format(self.target, self.payment)
        self.nickname = 'bithumb'+'_'+str(id)+'_'+self.symbol
        self.targetBalance = 0
        self.baseBalance   = 0
        self.targetBalanceTot = 0
        self.baseBalanceTot = 0
        self.bids_qty = 0
        self.bids_price = 0
        self.asks_qty = 0
        self.asks_price = 0
        self.GET_TIME_OUT = 30
        self.POST_TIME_OUT = 60

        self.connect_key = key
        self.secret_key  = secret

    def get_signature(self, encoded_payload, secret_key):
        signature = hmac.new(secret_key, encoded_payload, hashlib.sha512)
        api_sign  = base64.b64encode(signature.hexdigest().encode('utf-8'))
        return api_sign

    def http_request(self, method, path, params=None, headers=None, auth=None):
        url = API_URL + path
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=self.GET_TIME_OUT)
                if response.status_code == 200:
                    response = response.json()
                    return response
                else:
                    logger.error('http_request_{}_{}_{}_{}'.format(method, url, params, response.text))
            if method == "POST":
                response = requests.post(url, data=params, headers=headers, timeout=self.POST_TIME_OUT)
                if response.status_code == 200:
                    response = response.json()
                    return response
                else:
                    logger.error('http_request_{}_{}_{}_{}'.format(method, url, params, response.text))
        except Exception as e:
            logger.error('http_request_{}_{}_{}'.format(url, params, e))

        return False

    def query(self, endpoint, params):
        endpoint_item_array = {
            "endpoint": endpoint
        }

        uri_array = dict(endpoint_item_array, **params)  # Concatenate the two arrays.
        e_uri_data = urllib.parse.urlencode(uri_array)

        # Api-Nonce information generation.
        nonce = str(int(time.time() * 1000))

        data = endpoint + chr(0) + e_uri_data + chr(0) + nonce
        utf8_data = data.encode('utf-8')

        secret_key  = self.secret_key
        utf8_secret_key = secret_key.encode('utf-8')

        headers = {
            'Content-Type' : 'application/x-www-form-urlencoded',
            'Api-Key'      : self.connect_key,
            'Api-Sign'     : self.get_signature(utf8_data, bytes(utf8_secret_key)),
            'Api-Nonce'    : nonce
        }

        res = self.http_request('POST', endpoint, params=e_uri_data, headers=headers)
        return res

    def Ticker(self):
        path = '/public/ticker' + '/' + self.symbol
        res = self.http_request('GET', path)
        if res == False:
            return False
        if isinstance(res, dict):
            if 'data' in res and res['data']:
                if 'closing_price' in res['data'] and res['data']['closing_price']:
                    ticker = float(res['data']['closing_price'])
                    return ticker
        return False

    def Orderbook(self):
        path = '/public/orderbook' + '/' + self.symbol
        res = self.http_request('GET', path)

        if res == False:
            return False
        try:
            if isinstance(res, dict):
                if 'data' in res and res['data']:
                    if 'asks' in res['data'] and res['data']['asks']:
                        self.asks_price = float(res['data']['asks'][0]['price'])
                        self.asks_qty = float(res['data']['asks'][0]['quantity'])
                    if 'bids' in res['data'] and res['data']['bids']:
                        self.bids_price = float(res['data']['bids'][0]['price'])
                        self.bids_qty = float(res['data']['bids'][0]['quantity'])
                    return True
        except Exception as ex:
            logger.error("Orderbook exception error %s" %ex)
        return False

    def Balance(self):
        path = '/info/balance' + '/' + self.target
        request = {
            'currency': 'ALL'
        }
        res = self.query(path, request)
        if not res:
            return False
        self.targetBalance = self.baseBalance = 0
        if isinstance(res, dict):
            if 'data' in res and res['data']:
                self.targetBalance = float(res['data'].get('available_' + self.target.lower(),0))
                self.baseBalance   = float(res['data'].get('available_' + self.payment.lower(),0))
                self.targetBalanceTot = float(res['data'].get('total_' + self.target.lower(), 0))
                self.baseBalanceTot = float(res['data'].get('total_' + self.payment.lower(), 0))
        return True

    def Order(self, price, qty, side):
        order_id = 0
        status   = 'ERROR'

        path = '/trade/place'
        request = {
                    "order_currency"    : self.target,
                    "payment_currency"  : self.payment,
                    "units"             : str(qty),
                    "price"             : ('%.8f' % price).rstrip('0').rstrip('.'),
                    "type"              : 'ask' if side == 'SELL' or side == 'sell' else 'bid'
        }
        content = self.query(path, request)
        if not content:
            return status, order_id, content

        try:
            if isinstance(content, dict):
                status = 'OK' if content['status'] == '0000' else 'ERROR'
                if status == 'OK' and 'order_id' in content:
                    order_id = content['order_id']  # string
                    if not order_id:
                        status = 'ERROR'
                        order_id = 0
        except Exception as ex:
            logger.debug('Order exception %s_%s' %(self.nickname, ex))

        return status, order_id, content

    def Order_info(self, order_id, qty, side):
        path = '/info/orders' + '/' + self.target
        request = {
            "order_id": order_id,  # option, if not exist, all pending orders info
            "type": 'ask' if side == 'SELL' or side == 'sell' else 'bid',
            "order_currency": self.target,
            "payment_currency" : self.payment,
        }
        res = self.query(path, request)
        if not res:
            return False
        return res

    def Order_detail(self, order_id, side): # 회원의 판/구매 체결 내역
        path = '/info/order_detail'
        request = {
                    "order_id"  : order_id,
                    "type": 'ask' if side == 'SELL' or side == 'sell' else 'bid',
                    "order_currency"  : self.target,
                    "payment_currency" : self.payment
                    }
        res = self.query(path, request)
        if not res:
            return False
        if isinstance(res, dict):
            if 'status' in res and res['status']:
                if res['status'] == '0000':
                    return res
                logger.debug('cancel false reason: %s' % res)
        return False

    def Cancel(self, order_id, price=0, side=None, qty=0):
        path = '/trade/cancel'
        request = {
            'type': 'ask' if side == 'SELL' or side == 'sell' else 'bid',
            'order_id': order_id,
            'order_currency': self.target,
            'payment_currency' : self.payment
        }
        res = self.query(path, request)
        if not res:
            return False
        if isinstance(res, dict):
            if 'status' in res and res['status']:
                if res['status'] == '0000' or res['status'] == '3000':
                    return True
                logger.debug('Cancel false reason: %s' % res)
        return False

    def review_order(self, order_id, _qty=0, side=None):
        units_traded = avg_price = fee = 0.0
        getcontext().prec = 10
        try:
            res = self.Order_info(order_id, _qty, side)
            if res["status"] == "0000":  # normal operation
                if 'data' in res and res['data']:
                    if isinstance(res['data'], list):
                       units_traded = float(res["data"][0]["units"].replace(',', '')) - float(res["data"][0]["units_remaining"].replace(',',''))
                       qty = float(res["data"][0]["units"].replace(',',''))
                       avg_price = 0.0
                       fee = 0.0
                       if units_traded == 0:     # unfilled
                           return "GO", units_traded, avg_price, fee
                       elif units_traded < qty:  # partial filled
                           return "NG", units_traded, avg_price, fee
                       else:                     # filled or cancel    -> invalid status, Go order_detail
                           return "SKIP", units_traded, avg_price, fee

            if res["status"] == "5600":   # order_id does not exist, ie filled or cancelled
                res = self.Order_detail(order_id, side)
                if not res:
                    logger.debug('order detail error %s' %res)
                    return
                status = res['data']['order_status']
                if  status == 'Cancel':
                    return "SKIP", 0, 0, 0
                elif status == 'Completed':
                    if 'contract' in res['data'] and res['data']['contract']:
                        contract = res['data']['contract']
                        units_traded = avg_price = fee = total = 0.0
                        for c in contract:
                            units_traded += float(c['units'].replace(',',''))
                            total += float(c['total'].replace(',','')) # units*price
                            fee += float(c['fee'].replace(',',''))
                        avg_price = float(D(total)/D(units_traded)) if units_traded else 0
                        fee       = float(fee)
                        return "SKIP", units_traded, avg_price, fee
                else:
                    logger.debug('illegal status in order_detail %s_%s' %(self.nickname, order_id))
                    return "NG", 0, 0, 0

            logger.debug("response error %s_%s".format(self.nickname, res))

        except Exception as ex:
            logger.debug(f"Exception error in review order {res}_{ex}_{self.nickname}")

        return False, 0, 0, 0
