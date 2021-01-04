import json
import random
import pytest
import requests

from google.cloud import ndb

from ..model.user import User, UserState
from ..model.telegramMarkup import TelegramMarkup

# For comparing strings that have a format string for datetime
# Datetime in testing environment and server need not be the same and honestly
# is good enough for testing
def looseCompare(dateStr: str, fmtStr: str):
    fmtStr = fmtStr.split()
    dateStr = dateStr.split()

    # Compare strings by tokens
    # Skip over tokens that contain a format string
    for x, y in zip(fmtStr, dateStr):
        if "{}" not in x and x != y:
            return False

    return True


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

        self.ndbClient = ndb.Client()

    # Sends to webhook URL
    # This imitates the Telegram API sending an update to the backend
    def sendToWebhook(self, json):
        url = f"{self.apiUrl}/webhook"
        resp = requests.post(url, json=json)

        assert resp.status_code == 200
        return resp

    # Spoofs Telegram Bot API update object shape
    # Backend actually uses the chat ID to identify users instead of the actual user ID
    def createUpdate(self, text, userId="TEST_CHATID"):

        # Minimal structure required
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

    #
    #   Test cases
    #

    # Tests error handling of empty messages
    def test_emptyMessage(self):
        update = self.createUpdate("")
        del update["message"]

        resp = self.sendToWebhook(update)
        assert resp.text == "Received update with no message component"

    def test_invalidUpdateObject(self):
        update = self.createUpdate("")
        del update["message"]["date"]

        resp = self.sendToWebhook(update)
        assert resp.text == "Invalid update object"

    # Tests response to non-text messages (update with no text component)
    def test_nonTextMessage(self):
        update = self.createUpdate("")
        del update["message"]["text"]

        resp = self.sendToWebhook(update)
        assert resp.json()["text"] == self.STRINGS["no_text_error"]

    # Tests invalid command handling
    def test_invalidCommand(self):
        update = self.createUpdate("/invalid")

        resp = self.sendToWebhook(update)
        assert resp.json()["text"] == self.STRINGS["invalid_input"]

    # Tests /start command
    def test_startCommand(self):
        update = self.createUpdate("/start")

        resp = self.sendToWebhook(update)
        assert resp.json()["text"] == self.STRINGS["SAF100"]

    # Tests /forcesubmit command
    def test_forcesubmitCommand(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.TEMP_DEFAULT})
            update = self.createUpdate("/forcesubmit", userKey.id())

            resp = self.sendToWebhook(update)
            assert looseCompare(resp.json()["text"], self.STRINGS["window_open"])
            assert resp.json()["reply_markup"] == TelegramMarkup.TemperatureKeyboard

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.TEMP_REPORT

    # Tests /remind command
    def test_remindCommand(self):
        # Preconfigured user
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {"status": UserState.TEMP_DEFAULT, "remindAM": 8, "remindPM": 15}
            )
            update = self.createUpdate("/remind", userKey.id())

            resp = self.sendToWebhook(update)
            assert looseCompare(
                resp.json()["text"],
                self.STRINGS["reminder_existing_config"]
                + self.STRINGS["reminder_change_config"].format("AM"),
            )
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderAmKeyboard

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.REMIND_SET_AM

