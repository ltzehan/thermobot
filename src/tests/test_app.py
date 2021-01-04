import json
import random
import pytest
import requests

from google.cloud import ndb

from ..stringConstants import StringConstants
from ..model.user import User, UserState
from ..model.telegramMarkup import TelegramMarkup

from .test_temptakingWrapper import TEST_URL, TEST_GROUPNAME

STRINGS = StringConstants().STRINGS

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
        assert resp.json()["text"] == STRINGS["no_text_error"]

    # Tests invalid command handling
    def test_invalidCommand(self):
        update = self.createUpdate("/invalid")

        resp = self.sendToWebhook(update)
        assert resp.json()["text"] == STRINGS["invalid_input"]

    # Tests /start command
    def test_startCommand(self):
        update = self.createUpdate("/start")

        resp = self.sendToWebhook(update)
        assert resp.json()["text"] == STRINGS["SAF100"]

    # Tests /forcesubmit command
    def test_forcesubmitCommand(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.TEMP_DEFAULT})
            update = self.createUpdate("/forcesubmit", userKey.id())

            resp = self.sendToWebhook(update)
            assert looseCompare(resp.json()["text"], STRINGS["window_open"])
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
                STRINGS["reminder_existing_config"]
                + STRINGS["reminder_change_config"].format("AM"),
            )
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderAmKeyboard

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.REMIND_SET_AM

        # No prior configuration
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.TEMP_DEFAULT})
            update = self.createUpdate("/remind", userKey.id())

            resp = self.sendToWebhook(update)
            assert looseCompare(
                resp.json()["text"],
                STRINGS["reminder_not_configured"]
                + STRINGS["reminder_change_config"].format("AM"),
            )
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderAmKeyboard

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.REMIND_SET_AM

    # Tests handling of INIT_START
    def test_INIT_START(self):

        # Test invalid URL
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_START})
            update = self.createUpdate("https://temptaking.ado.sg/group", userKey.id())

            resp = self.sendToWebhook(update)
            assert resp.json()["text"] == STRINGS["invalid_url"]

        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_START})
            update = self.createUpdate(TEST_URL, userKey.id())

            resp = self.sendToWebhook(update)
            assert looseCompare(resp.json()["text"], STRINGS["group_msg"])
            assert (
                resp.json()["reply_markup"] == TelegramMarkup.GroupConfirmationKeyboard
            )

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.INIT_CONFIRM_URL
            assert user.groupName == TEST_GROUPNAME
            assert user.groupMembers

    # Tests handling of INIT_CONFIRM_URL
    def test_INIT_CONFIRM_URL(self):

        # Minimal state required
        def _createUser() -> ndb.Key:
            return self.createUser(
                {
                    "status": UserState.INIT_CONFIRM_URL,
                    "groupId": "TEST_GROUPID",
                    "groupName": "TEST_GROUPNAME",
                    "groupMembers": json.dumps(
                        [{"id": "TEST_MEMBERID", "identifier": "TEST_MEMBERNAME",}]
                    ),
                }
            )

        # Test wrong group URL response
        with self.ndbClient.context() as context:
            userKey = _createUser()
            update = self.createUpdate(STRINGS["group_keyboard_no"], userKey.id())

            resp = self.sendToWebhook(update)
            assert resp.json()["text"] == STRINGS["SAF100_2"]

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.INIT_START

        # Test unexpected response (not in keyboard)
        with self.ndbClient.context() as context:
            userKey = _createUser()
            update = self.createUpdate(
                "I don't know how to press buttons", userKey.id()
            )

            resp = self.sendToWebhook(update)
            assert resp.json()["text"] == STRINGS["use_keyboard"]
            assert (
                resp.json()["reply_markup"] == TelegramMarkup.GroupConfirmationKeyboard
            )

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.INIT_CONFIRM_URL

        # Test correct group URL response (<300 members)
        with self.ndbClient.context() as context:
            userKey = _createUser()
            update = self.createUpdate(STRINGS["group_keyboard_yes"], userKey.id())

            resp = self.sendToWebhook(update)
            assert resp.json()["text"].startswith(STRINGS["member_msg_1"])

            context.clear_cache()
            user: User = userKey.get()
            groupMembers = json.loads(user.groupMembers)

            assert resp.json()["reply_markup"] == TelegramMarkup.NameSelectionKeyboard(
                [x["identifier"] for x in groupMembers]
            )
            assert user.status == UserState.INIT_GET_NAME

        # Test correct group URL response (member overflow)
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {
                    "status": UserState.INIT_CONFIRM_URL,
                    "groupId": "TEST_GROUPID",
                    "groupName": "TEST_GROUPNAME",
                    # Create 400 members to overflow
                    "groupMembers": json.dumps(
                        [
                            {
                                "id": f"TEST_MEMBERID_{i}",
                                "identifier": f"TEST_MEMBERNAME_{i}",
                            }
                            for i in range(400)
                        ]
                    ),
                }
            )
            update = self.createUpdate(STRINGS["group_keyboard_yes"], userKey.id())

            resp = self.sendToWebhook(update)
            assert resp.json()["text"] == STRINGS["member_overflow"].format(400)

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.INIT_GET_NAME
