#!/usr/bin/env python
# trading demo program between bithumb and coinone.

import logging
import logging.handlers
import time

from bithumb import Bithumb
from coinone import Coinone
from telegram import Telegram

from configparser import ConfigParser

class Coin(object):
    def __init__(self):
        self.trade_max_volume = 0
        self.trade_min_thresh = 0 # unconditional trade
        self.targetSum        = 0
        self.baseSum          = 0
        self.target           = 'BTC'
        self.base             = 'KRW'
        self.profit = 0
        self.hit = 0
        self.temp_interval    =  0
        self.update_delay     = 10  # sec
        self.last_update      = 0
        self.bithumb_enabled  = False
        self.traded           = False
        self.dryrun           = 0   # 1: simultation, 0 : real
        self.rate             = 1.001
        self.interval         = 5
        self.max              = 0
        self.thresh           = 0
        self.loop_number      = 0
        self.observer         = None


    def cal_profit(self, _from, _to):
        #from: ask market, buy  exchanger
        #to  : bid market, sell exchanger

        #determine tradesize
        TradeSize = min(_from.asks_qty, _to.bids_qty, self.trade_max_volume)

        SellBalance = _to.targetBalance
        BuyBalance  = _from.baseBalance

        if TradeSize > SellBalance :
            TradeSize = SellBalance
        if TradeSize * _from.asks_price > BuyBalance :
            TradeSize = BuyBalance / _from.asks_price
        TradeSize = int(TradeSize) #truncate under point
        Profit    = TradeSize *(_to.bids_price - _from.asks_price) - TradeSize*2*0.001
        return TradeSize, Profit

    def main(self):

        # Create Logger
        logger = logging.getLogger()
        logger.setLevel(logging.NOTSET)
        # Create console handler and set level to debug
        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        # Create file handler and set level to debug
        fh = logging.FileHandler('mylog.txt', mode='a')
        fh.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter('[%(asctime)s] [%(name)s:%(lineno)s] %(message)s')
        # Add formatter to handlers
        sh.setFormatter(formatter)
        fh.setFormatter(formatter)

        # Add handlers to logger
        logger.addHandler(sh)
        logger.addHandler(fh)

        # Load Config File
        config = ConfigParser()
        config.read('trading.conf')

        bithumbKey = config.get('ArbBot', 'bithumbKey')
        bithumbSecret = config.get('ArbBot', 'bithumbSecret')
        coinoneKey = config.get('ArbBot', 'coinoneKey')
        coinoneSecret = config.get('ArbBot', 'coinoneSecret')

        chat_id = config.get('ChatBot', 'chatId')
        chat_token = config.get('ChatBot', 'chatToken')

        self.trade_max_volume = float(config.get(self.target, 'TRADE_MAX_VOLUME'))
        self.trade_min_thresh = float(config.get(self.target,'TRADE_MIN_THRESH'))

        self.dryrun = int(config.get('ArbBot', 'dryrun'))

        # Create Exchange API Objects
        bithumb = Bithumb(self.target, self.base, bithumbKey, bithumbSecret)
        coinone = Coinone(self.target, self.base, coinoneKey, coinoneSecret)

        # Observer Objets
        tg = Telegram(chat_token, chat_id)
        tg.message("Welcome to trading world !!!")
        # Main Loop

        #check balance bithumb and coinone
        print("===check balance")
        response = bithumb.Balance()
        if response == True:
            logging.info("**{} : (tBal: {:.8f}) | (pBal: {:.4f})**"
                  .format("bithumb", bithumb.targetBalance, bithumb.baseBalance))
        else:
            logging.error(f"bithumb balance read fail_{response}")
            return

        #coinone
        response = coinone.Balance()
        if response == True:
            logging.info("**{} : (tBal: {:.8f}) | (pBal: {:.4f})**"
                         .format("coinone", coinone.targetBalance, coinone.baseBalance))
        else:
            logging.error(f"coinone balance read fail_{response}")
            return

        if self.dryrun:
            bithumb.targetBalance = 100
            bithumb.baseBalance   = 100000000
            coinone.targetBalance = 100
            coinone.baseBalance   = 100000000

        while True:
            #check price the target
            response = bithumb.Orderbook()
            if response == True:
                logging.info("**{} : ask {:.0f} bid {:.0f} asks_qty {:.4f} bids_qty {:.4f}"
                             .format("bithumb", bithumb.asks_price, bithumb.bids_price, \
                                     bithumb.asks_qty, bithumb.bids_qty))
            else:
                logging.error(f"bithumb orderbook read fail_{response}")


            response = coinone.Orderbook()
            if response == True:                
                logging.info("**{} : ask {:.0f} bid {:.0f} asks_qty {:.4f} bids_qty {:.4f}"
                             .format("coinone", coinone.asks_price,coinone.bids_price, \
                             coinone.asks_qty,coinone.bids_qty ))
            else:
                logging.error(f"coinone orderbook read fail_{response}")

            #test s
            # bithumb.asks_price = 950
            # coinone.bids_price = 960
            #test e

            #find the chance
            TradeSize = 0
            if bithumb.asks_price < coinone.bids_price:
                logging.info("do trading bithumb buy coinone sell !!!")
                TradeSize, Profit = self.cal_profit(bithumb, coinone)
                if TradeSize > self.trade_min_thresh and Profit > 0:
                    print("start trading1 TS[%d] Profit[%d]" % (TradeSize, Profit))
                    if not self.dryrun:
                        # price, qty, side
                        result_b = bithumb.Order(price=bithumb.asks_price, qty=TradeSize, side='BUY')
                        print(f'bithumb_{result_b}_BUY_{TradeSize}@{bithumb.asks_price}')
                        result_c = coinone.Order(price=coinone.bids_price, qty=TradeSize, side='SELL')
                        print(f'coinone_{result_c}_SEL_{TradeSize}@{coinone.bids_price}')
                        tg.message(f"Bithumb buy_{TradeSize}@{bithumb.asks_price}\n\rCoinone sell_{TradeSize}@{coinone.bids_price}")
                else:
                    print("skip trading1 TS[%d] Profit[%d]" %(TradeSize, Profit))
            elif coinone.asks_price < bithumb.bids_price:
                logging.info("do trading coinone buy bithumb sell !!!")
                TradeSize, Profit = self.cal_profit(coinone, bithumb)
                if TradeSize > self.trade_min_thresh and Profit > 0:
                    print("start trading2 TS[%d] Profit[%d]" % (TradeSize, Profit))
                    if not self.dryrun:
                        result_c = coinone.Order(price=coinone.asks_price, qty=TradeSize, side='BUY')
                        print(f'coinone_{result_c}_BUY_{TradeSize}@{coinone.asks_price}')
                        result_b = bithumb.Order(price=bithumb.bids_price, qty=TradeSize, side='SELL')
                        print(f'bithumb_{result_b}_SEL_{TradeSize}@{bithumb.bids_price}')
                        tg.message(
                            f"Coinone buy_{TradeSize}@{coinone.asks_price}\n\rBithumb sell_{TradeSize}@{bithumb.bids_price}")
                else:
                    print("skip trading2 TS[%d] Profit[%d]" % (TradeSize, Profit))
            else:
                logging.info("..")

            time.sleep(5)

if __name__ == "__main__":
    print("Arbitrage start")
    coin = Coin()
    coin.main()