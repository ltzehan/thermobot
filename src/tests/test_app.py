import json
import random
import pytest
import requests
from unittest import mock


class TestBot:
    # Initialization for tests
    def setup_class(self):

        # Load secrets
        with open("secrets.json") as tf:
            SECRET = json.load(tf)

        PROJECT_URL = SECRET["project-url"]
        BOT_TOKEN = SECRET["telegram-bot"]

        self.apiUrl = f"{PROJECT_URL}/{BOT_TOKEN}"

        # Load strings
        with open("strings.json", encoding="utf-8") as tf:
            self.STRINGS = json.load(tf)

    # Sends to webhook URL
    # This imitates the Telegram API sending an update to the backend
    def sendToWebhook(self, json):
        url = f"{self.apiUrl}/webhook"
        resp = requests.post(url, json=json)

        return resp

    # Spoofs Telegram Bot API update object shape
    def createUpdate(self, text):

        # Minimal structure required
        return {
            "update_id": "TEST_UPDATEID",
            "message": {
                "message_id": "TEST_MSGID",
                "date": "TEST_DATE",
                "from": {"id": "TEST_USERID", "first_name": "TEST_USERFIRSTNAME"},
                "chat": {"id": "TEST_CHATID"},
                "text": text,
            },
        }

    #
    #   Test cases
    #

    # Tests error handling of empty messages
    def test_emptyMessage(self):
        update = self.createUpdate("")
        del update["message"]

        resp = self.sendToWebhook(update)
        assert resp.status_code == 200
        assert resp.text == "Received update with no message component"

    def test_invalidUpdateObject(self):
        update = self.createUpdate("")
        del update["message"]["date"]

        resp = self.sendToWebhook(update)
        assert resp.status_code == 200
        assert resp.text == "Invalid update object"

    # Tests response to non-text messages (update with no text component)
    def test_nonTextMessage(self):
        update = self.createUpdate("")
        del update["message"]["text"]

        resp = self.sendToWebhook(update)
        assert resp.status_code == 200
        assert resp.json()["text"] == self.STRINGS["no_text_error"]

    # Tests invalid command handling
    def test_invalidCommand(self):
        update = self.createUpdate("/invalid")

        resp = self.sendToWebhook(update)
        assert resp.status_code == 200
        assert resp.json()["text"] == self.STRINGS["invalid_input"]

    # Tests /start command
    def test_startCommand(self):
        update = self.createUpdate("/start")

        resp = self.sendToWebhook(update)
        assert resp.status_code == 200
        assert resp.json()["text"] == self.STRINGS["SAF100"]
