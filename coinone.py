import hashlib, base64, json
from operator import itemgetter
import requests
import threading
import hmac
import time

from decimal import Decimal as D
from decimal import getcontext

import logging

logger = logging.getLogger(__name__)

API_URL = 'https://api.coinone.co.kr'


class Coinone(object):

    def __init__(self, target, payment, key, secret):
        self.target = target.upper()
        self.payment = payment.upper()
        self.symbol = '%s-%s' % (self.target, self.payment)
        self.nickname = 'coinone' + '_' + str(id) + '_' + self.symbol
        self.targetBalance = 0
        self.baseBalance = 0
        self.targetBalanceTot = 0
        self.baseBalanceTot = 0
        self.bids_qty = 0
        self.bids_price = 0
        self.asks_qty = 0
        self.asks_price = 0

        # anti Hacker
        self.sell_list = []
        self.buy_list = []

        self.GET_TIME_OUT = 30
        self.POST_TIME_OUT = 60

        self.connect_key = key
        self.secret_key = secret

        self.access_token = ''
        self.expires_in = 0
        self.old_expire = 0

        self.blocked_user = {'result':'error', 'errorCode':'4', 'errorMsg': 'Blocked user access.'}


    def http_request(self, method, path, params=None, headers=None, auth=None):
        url = API_URL + path
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=self.GET_TIME_OUT)
                if response.status_code == 200 :
                    response = response.json()
                    return response
                else:
                    logger.debug('http_request_{}_{}_{}_{}'.format(method, url, params, response.json()))
            if method == "POST":
                response = requests.post(url, data=params, headers=headers, timeout=self.POST_TIME_OUT)
                if response.status_code == 200:
                    response = response.json()
                    return response
                elif response.status_code == 429 : # blcoked user
                    return self.blocked_user
                else:
                    logger.debug('http_request_{}_{}_{}_{}'.format(method, url, response.json()))
        except Exception as e:
            logger.error('http_request_{}_{}_{}'.format(url, params, e))

        return False

    def get_encoded_payload(self, payload):
        payload['nonce'] = int(time.time() * 1000)

        dumped_json = json.dumps(payload)
        encoded_json = base64.b64encode(bytes(dumped_json, 'utf-8'))
        return encoded_json

    def get_signature(self, encoded_payload):
        SECRET_KEY = bytes(self.secret_key, 'utf-8')
        signature = hmac.new(SECRET_KEY, encoded_payload, hashlib.sha512)
        return signature.hexdigest()

    def Ticker(self):
        path = '/ticker/'
        request = {
            'currency': self.target
        }
        try:
            res = self.http_request('GET', path, request)
            if res is False:
                return False
            if isinstance(res, dict):
                if 'last' in res and res['last']:
                    ticker = float(res['last'])
                    return ticker
        except Exception as ex:
            logger.error("Ticker exception error %s" % ex)
        return False

    def Orderbook(self):
        path = '/orderbook/'
        request = {
            'currency': self.target
        }
        try:
            res = self.http_request('GET', path, request)
            if not res:
                return False

            buy_list = []
            sell_list = []

            if isinstance(res, dict):
                if 'bid' in res and res['bid']:
                    for o in res['bid']:
                        price = float(o['price'])
                        qty = float(o['qty'])
                        buy_list.append([price, qty])
                if 'ask' in res and res['ask']:
                    for o in res['ask']:
                        price = float(o['price'])
                        qty = float(o['qty'])
                        sell_list.append([price, qty])
                if buy_list:
                    buy_list.sort(key=itemgetter(0), reverse=True)
                    self.bids_price = buy_list[0][0]
                    self.bids_qty = buy_list[0][1]
                if sell_list:
                    sell_list.sort(key=itemgetter(0))
                    self.asks_price = sell_list[0][0]
                    self.asks_qty = sell_list[0][1]
                return True
        except Exception as ex:
            logger.error("Orderbook exception error %s" % ex)

        return False

    def Balance(self):
        try:
            path = '/v2/account/balance/'
            payload = {
                'access_token': self.connect_key
            }
            encoded_payload = self.get_encoded_payload(payload)
            headers = {
                'Content-type': 'application/json',
                'X-COINONE-PAYLOAD': encoded_payload,
                'X-COINONE-SIGNATURE': self.get_signature(encoded_payload),
            }

            res = self.http_request('POST', path, encoded_payload, headers=headers)
            if not res:
                return False
            # self.targetBalance = self.baseBalance = 0  # afraid that balances is zeros
            target = self.target.lower()
            payment = self.payment.lower()
            if isinstance(res, dict):
                if target in res and res[target]:
                    self.targetBalance = float(res[target].get('avail', 0.0))
                    self.targetBalanceTot = float(res[target].get('balance', 0.0))
                if payment in res and res[payment]:
                    self.baseBalance = float(res[payment].get('avail', 0.0))
                    self.baseBalanceTot = float(res[payment].get('balance', 0.0))
                return True  # only assest is displayed above 0

        except Exception as ex:
            logger.error(f'Exception occur in balance_{self.nickname}')

        return False

    def Order(self, price, qty, side):
        try:
            order_id = 0
            status = 'ERROR'

            if side == 'BUY':
                path = '/v2/order/limit_buy/'
                payload = {
                    'access_token': self.connect_key,
                    'price': price,
                    'qty': qty,
                    'currency': self.target,
                }
            else:
                path = '/v2/order/limit_sell/'
                payload = {
                    'access_token': self.connect_key,
                    'price': price,
                    'qty': qty,
                    'currency': self.target,
                }
            encoded_payload = self.get_encoded_payload(payload)
            headers = {
                'Content-type': 'application/json',
                'X-COINONE-PAYLOAD': encoded_payload,
                'X-COINONE-SIGNATURE': self.get_signature(encoded_payload),
            }
            content = self.http_request('POST', path, encoded_payload, headers=headers)
            if not content:
                return 'ERROR', order_id, content

            if isinstance(content, dict):
                # status = 'OK' if 'result' in content and content['result'] == 'success' else 'ERROR'
                if 'result' in content and content['result'] == 'success':
                    status = 'OK'
                if status == 'OK' and content['orderId']:
                    order_id = content['orderId']  # string
                    if not order_id:
                        status = 'ERROR'
                        order_id = 0
        except Exception as ex:
            logger.error(f'Exception occur in Order_{self.nickname}')

        return status, order_id, content

    def Cancel(self, order_id, price=0, side=None, qty=0): #jmpark1
        try:
            path = '/v2/order/cancel/'
            payload = {
                'access_token': self.connect_key,
                'order_id': order_id,
                'price': price,
                'qty': qty,
                'is_ask': 1 if side == 'SELL' else 0,
                'currency': self.target,
            }

            for cnt in range(10):
                time.sleep(10*cnt)
                encoded_payload = self.get_encoded_payload(payload)

                headers = {
                    'Content-type': 'application/json',
                    'X-COINONE-PAYLOAD': encoded_payload,
                    'X-COINONE-SIGNATURE': self.get_signature(encoded_payload),
                }
                if order_id == 'None':
                    logger.error(f'Order_id error_{order_id}_{self.nickname}')
                    return False
                res = self.http_request('POST', path, encoded_payload, headers=headers)
                if res == False:
                    return False

                if isinstance(res, dict):
                    if 'result' in res and res['result']:
                        if res['result'] == 'success':
                            return True
                        else:
                            if 'errorCode' in res and res['errorCode']:
                                if res['errorCode'] == '104':
                                    return True  # Order id is not exist(이미 취소된 거래)
                                elif res['errorCode'] == '4': # user blocked by too many requests
                                    logger.debug(f'Too many requests_{self.nickname}')
                                elif res['errorCode'] == '116': # Already Traded
                                    logger.debug(f'Already Traded_{qty}@{price}_{side}_{order_id[:10]}_{self.nickname}')
                                    return True
                                elif res['errorCode'] == '117': # Already Cancel
                                    logger.debug(f'Already Cancel_{qty}@{price}_{side}_{order_id[:10]}_{self.nickname}')
                                    return True
                                elif res['errorCode'] == '107':
                                    logger.debug(f'Parameter_{qty}@{price}_{side}_{order_id[:10]}_{self.nickname}')
                                    return False
                                else:
                                    logger.debug(f'{res["errorCode"]}_{res["errorMsg"]}')
                            else:
                                logger.debug('cancel false reason: %s_%s' % (res['errorCode'], res['errorMsg']))

        except Exception as ex:
            logger.error(f'Exception occur in cancel_{ex}_{self.nickname}')

        return False

    def Order_info(self, order_id):
        '''
        특정 order id 에 대한 상태 정보
        '''
        path = '/v2/order/order_info/'
        payload = {
            'access_token': self.connect_key,
            'order_id': order_id,
            'currency': self.target,
        }
        encoded_payload = self.get_encoded_payload(payload)
        headers = {
            'Content-type': 'application/json',
            'X-COINONE-PAYLOAD': encoded_payload,
            'X-COINONE-SIGNATURE': self.get_signature(encoded_payload),
        }

        res = self.http_request('POST', path, encoded_payload, headers=headers)
        if not res:
            return False

        return res

    def review_order(self, order_id, _qty=0, side=None):

        units_traded = avg_price = fee = 0
        resp = None
        getcontext().prec = 10
        try:
            res = self.Order_info(order_id)
            if isinstance(res, dict):
                if 'result' in res and res['result']:
                    if res['result'] == 'success':
                        if 'info' in res and res['info']:
                            units_traded = float(D(res['info']['qty']) - D(res['info']['remainQty']))
                            avg_price    = float(D(res['info']['price'])/D(_qty)) if _qty else 0
                            fee = float(res['info']['fee'])
                            status       = res['status']

                            # logger.debug(f'{units_traded}_{avg_price}_{status}_{self.nickname}')

                            if  units_traded == 0 :   # unfilled
                                return "GO", units_traded, avg_price, fee
                            elif units_traded < _qty : #partially filled
                                return "NG", units_traded, avg_price, fee
                            else:  # filled or canceled
                                return "SKIP", units_traded, avg_price, fee
                    else:
                        if 'errorCode' in res and res['errorCode']:
                            if res['errorCode'] == '104' : # order id not exist
                                return "SKIP", units_traded, avg_price, fee

            logger.debug(f"response error {self.nickname}_{res}")

        except Exception as ex:
            logger.debug(f"response error {self.nickname}_{res}")

        return False, 0, 0, 0
