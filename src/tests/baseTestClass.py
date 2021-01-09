import json
import random
import requests

from google.cloud import ndb

from ..model.user import User

# Base class with useful methods for implementing test cases
class BaseTestClass:

    # Initialization for tests
    def setup_class(self):

        # Load secrets
        with open("secrets.json") as tf:
            SECRET = json.load(tf)

        PROJECT_URL = SECRET["project-url"]
        BOT_TOKEN = SECRET["telegram-bot"]

        self.apiUrl = f"{PROJECT_URL}/{BOT_TOKEN}"
        self.ndbClient = ndb.Client()

    # Sends to the base URL
    def sendToBase(self, endpoint: str, json):
        url = f"{self.apiUrl}/{endpoint}"
        resp = requests.post(url, json=json)

        assert resp.status_code == 200
        return resp

    # Sends to webhook URL
    # This imitates the Telegram API sending an update to the backend
    def sendToWebhook(self, json):
        return self.sendToBase("webhook", json)

    # Spoofs Telegram Bot API update object shape
    # Backend actually uses the chat ID to identify users instead of the actual user ID
    def createUpdate(self, text, userId="TEST_CHATID"):
        return {
            "update_id": "TEST_UPDATEID",
            "message": {
                "message_id": "TEST_MSGID",
                "date": "TEST_DATE",
                "from": {"id": "TEST_USERID", "first_name": "TEST_USERFIRSTNAME"},
                "chat": {"id": userId},
                "text": text,
            },
        }

    # Creates new randomized User for test
    def createUser(self, prop: dict = {}) -> ndb.Key:
        uid = str(random.randint(0, 1e10))
        user = User.get_or_insert(uid, **prop)
        user.put()

        return user.key
