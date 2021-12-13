
import sys
import time
import base64
import hmac, hashlib
import urllib.parse
import urllib.request
import requests

API_URL = 'https://api.bithumb.com'

class Bithumb(object):
    def __init__(self, target, payment, key, secret):
        self.target = target.upper()
        self.payment = payment.upper()
        self.symbol = "{}_{}".format(self.target, self.payment)
        self.connect_key = key
        self.secret_key  = secret
        self.GET_TIME_OUT = 30
        self.POST_TIME_OUT = 60

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
                    print('http_request_{}_{}_{}_{}'.format(method, url, params, response.text))
            if method == "POST":
                response = requests.post(url, data=params, headers=headers, timeout=self.POST_TIME_OUT)
                if response.status_code == 200:
                    response = response.json()
                    return response
                else:
                    print('http_request_{}_{}_{}_{}'.format(method, url, params, response.text))
        except Exception as e:
            print('http_request_{}_{}_{}'.format(url, params, e))

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

        return res

    def Orderbook(self):
        path = '/public/orderbook' + '/' + self.symbol
        res = self.http_request('GET', path)

        if res == False:
            return False

        return res

    def Balance(self):
        path = '/info/balance' + '/' + self.target
        request = {
            'currency': 'ALL'
        }
        res = self.query(path, request)
        if not res:
            return False
        return res

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

        return res
    
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
                print('Cancel false reason: %s' % res)
        return False


bithumbkey    = ''
bithumbsecret = ''

target = 'XRP'
payment = 'BTC'

bithumb = Bithumb(target='XRP', payment='BTC', key=bithumbkey, secret=bithumbsecret)

res = bithumb.Ticker()
ticker = float(res['data']['closing_price'])
print(ticker)




