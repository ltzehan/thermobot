import json
import requests


class TelegramApiWrapper:
    def __init__(self, token):
        self.token = token

    # Sends a POST request with a JSON payload to the specified URL
    # Returns the JSON response
    def _postJson(self, json, url):
        r = requests.post(url, json=json)
        return r.json()

    # Returns the endpoint URL corresponding to the method
    def _makeApiUrl(self, method) -> str:
        return "https://api.telegram.org/bot{}/{}".format(self.token, method)

    # Sends a message represented in JSON
    def sendMessage(self, json):
        return self._postJson(json, self._makeApiUrl("sendMessage"))

    def getMe(self):
        return self._postJson({}, self._makeApiUrl("getMe"))

    def setWebhook(self, webhookUrl):
        return self._postJson({"url": webhookUrl}, self._makeApiUrl("setWebhook"))

    def clearWebhook(self):
        return self.setWebhook("")
