#!/usr/bin/env python
# coding: utf-8
import requests

API_URL = "https://api.telegram.org/bot"

class Telegram(object):

    def __init__(self, key, chat_id) :
        self.key = key
        self.chat_id = chat_id
        self.markdown = False
        self.html = False

    def get_me(self):
        url = API_URL + self.key + "/getMe"
        resp = requests.get(url)
        return resp.json()

    def get_updates(self):
        url = API_URL + self.key + "/getUpdates"
        resp = requests.get(url)
        return resp.json()

    def message(self, message):
        url = API_URL + self.key + "/sendMessage"
        params = {
                  "chat_id": self.chat_id,
                  "text": message
        }
        if self.markdown or self.html:
            parse_mode = "HTML"
            if self.markdown:
                parse_mode = "Markdown"
            params["parse_mode"] = parse_mode
        resp = requests.post(url, params=params)
        content = resp.json()
        return content

if __name__ == "__main__":
    # Load Config File
    from configparser import ConfigParser, NoSectionError
    # Load Config File
    config = ConfigParser()
    config.read('trading.conf')
    chat_id    = config.get('ChatBot', 'chatId')
    chat_token = config.get('ChatBot', 'chatToken')

    tg = Telegram(chat_token, chat_id)
    result = tg.message("welcome to my telegram message service")
    print(result)