import json
import random
import pytest
import requests

from google.cloud import ndb

from ..stringConstants import StringConstants
from ..model.user import User, UserState
from ..model.telegramMarkup import TelegramMarkup

from .test_temptakingWrapper import *

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


class TestApp(BaseTestClass):

    # Tests error handling of empty messages
    def test_emptyMessage(self):
        update = self.createUpdate("")
        del update["message"]

        resp = self.sendToWebhook(update)
        assert resp.text == "Received update with no message component"

    def test_invalidUpdateObject(self):
        update = self.createUpdate("", "")
        del update["message"]["date"]

        resp = self.sendToWebhook(update)
        assert resp.text == "Invalid update object"

    # Tests response to non-text messages (update with no text component)
    def test_nonTextMessage(self):
        update = self.createUpdate("")
        del update["message"]["text"]

        resp = self.sendToWebhook(update)
        assert resp.json()["text"] == STRINGS["no_text_error"]


class TestUpdateHandler(BaseTestClass):

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
            userKey = self.createUser(
                {"status": UserState.TEMP_DEFAULT, "temp": User.TEMP_NONE}
            )
            update = self.createUpdate("/forcesubmit", userKey.id())

            resp = self.sendToWebhook(update)
            assert looseCompare(resp.json()["text"], STRINGS["window_open"])
            assert resp.json()["reply_markup"] == TelegramMarkup.TemperatureKeyboard

            context.clear_cache()
            user: User = userKey.get()
            assert user.temp == User.TEMP_NONE

    # Tests /remind command for preconfigured user
    def test_remindCommand_withConfig(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {"status": UserState.TEMP_DEFAULT, "remindAM": 8, "remindPM": 15}
            )
            update = self.createUpdate("/remind", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["reminder_existing_config"].format(
                f"{user.remindAM:02}:01", f"{user.remindPM:02}:01"
            ) + STRINGS["reminder_change_config"].format("AM")
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderAmKeyboard

            assert user.status == UserState.REMIND_SET_AM

    # Tests /remind command for user with no prior configuration
    def test_remindCommand_noConfig(self):
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

    # Tests querying of user for their name (< 300 members)
    def test_queryMemberName(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {
                    "status": UserState.INIT_CONFIRM_URL,
                    "groupId": TEST_GROUPID,
                    "groupName": TEST_GROUPNAME,
                    "groupMembers": json.dumps(
                        [{"id": "TEST_MEMBERID", "identifier": "TEST_MEMBERNAME",}]
                    ),
                }
            )
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
    def test_queryMemberName_overflow(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {
                    "status": UserState.INIT_CONFIRM_URL,
                    "groupId": TEST_GROUPID,
                    "groupName": TEST_GROUPNAME,
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


# Tests handling of INIT_START
class TestInitStart(BaseTestClass):

    # Test invalid URL given
    def test_invalidUrl(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_START})
            update = self.createUpdate("https://temptaking.ado.sg/group", userKey.id())

            resp = self.sendToWebhook(update)
            assert resp.json()["text"] == STRINGS["invalid_url"]

    # Test valid URL given
    def test_validUrl(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_START})
            update = self.createUpdate(TEST_URL, userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["group_msg"].format(user.groupName)
            assert (
                resp.json()["reply_markup"] == TelegramMarkup.GroupConfirmationKeyboard
            )

            assert user.status == UserState.INIT_CONFIRM_URL
            assert user.groupName == TEST_GROUPNAME
            assert user.groupMembers


# Tests handling of INIT_CONFIRM_URL
class TestInitConfirmUrl(BaseTestClass):

    # Minimal state required
    def _createUser(self) -> ndb.Key:
        return self.createUser(
            {
                "status": UserState.INIT_CONFIRM_URL,
                "groupId": TEST_GROUPID,
                "groupName": TEST_GROUPNAME,
                "groupMembers": json.dumps(
                    [{"id": "TEST_MEMBERID", "identifier": "TEST_MEMBERNAME",}]
                ),
            }
        )

    # Test wrong group URL response
    def test_wrongUrl(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate(STRINGS["group_keyboard_no"], userKey.id())

            resp = self.sendToWebhook(update)
            assert resp.json()["text"] == STRINGS["SAF100_2"]

            context.clear_cache()
            user: User = userKey.get()
            assert user.status == UserState.INIT_START

    # Test invalid response (not in keyboard)
    def test_invalidResponse(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
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


# Tests handling of INIT_GET_NAME
class TestInitGetName(BaseTestClass):

    # Minimal state required
    def _createUser(self) -> ndb.Key:
        return self.createUser(
            {
                "status": UserState.INIT_GET_NAME,
                "groupId": TEST_GROUPID,
                "groupName": TEST_GROUPNAME,
                "groupMembers": json.dumps(
                    [
                        {
                            "id": "TEST_MEMBERID",
                            "identifier": "TEST_MEMBERNAME",
                            "hasPin": "True",
                        }
                    ]
                ),
            }
        )

    # Test valid name given
    def test_validName(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("TEST_MEMBERNAME", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["member_msg_2"].format(
                user.memberName
            )
            assert (
                resp.json()["reply_markup"] == TelegramMarkup.MemberConfirmationKeyboard
            )

            assert user.status == UserState.INIT_GET_PIN
            assert user.memberId == "TEST_MEMBERID"
            assert user.memberName == "TEST_MEMBERNAME"

    # Test invalid name given
    def test_invalidName(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("TEST_FAIL", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            # Other tests handled by test_queryMemberName
            assert resp.json()["text"].startswith(STRINGS["member_msg_1"])
            assert user.status == UserState.INIT_GET_NAME


# Test handling of INIT_GET_PIN
class TestInitGetPin(BaseTestClass):

    # Minimal state required
    def _createUser(self, hasPin: bool, pinState: str) -> ndb.Key:
        return self.createUser(
            {
                "status": UserState.INIT_GET_PIN,
                "groupId": TEST_GROUPID,
                "groupName": TEST_GROUPNAME,
                "groupMembers": json.dumps(
                    [
                        {
                            "id": "TEST_MEMBERID",
                            "identifier": "TEST_MEMBERNAME",
                            "hasPin": hasPin,
                        }
                    ]
                ),
                "pin": pinState,
            }
        )

    # Tests incorrect name
    def test_incorrectName(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(hasPin=True, pinState="True")
            update = self.createUpdate(STRINGS["member_keyboard_no"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            # Other tests handled by test_queryMemberName
            assert resp.json()["text"].startswith(STRINGS["member_msg_1"])
            assert user.status == UserState.INIT_GET_NAME
            assert user.pin != User.PIN_MEMBER_CONFIRMED

    # Tests correct name and PIN already set
    def test_correctName_pinSet(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(hasPin=True, pinState="True")
            update = self.createUpdate(STRINGS["member_keyboard_yes"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["pin_msg_1"]
            assert user.status == UserState.INIT_CONFIRM_PIN
            assert user.pin == User.PIN_MEMBER_CONFIRMED

    # Tests correct name but PIN not yet set
    def test_correctName_noPin(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(hasPin=False, pinState="False")
            update = self.createUpdate(STRINGS["member_keyboard_yes"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["set_pin_1"].format(user.groupId)
            assert resp.json()["reply_markup"] == TelegramMarkup.PinConfiguredKeyboard
            assert user.status == UserState.INIT_GET_PIN
            assert user.pin == User.PIN_MEMBER_CONFIRMED

    # Tests invalid response (not in keyboard)
    def test_invalidResponse(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(hasPin=True, pinState="True")
            update = self.createUpdate("invalid response", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["use_keyboard"]
            assert (
                resp.json()["reply_markup"] == TelegramMarkup.MemberConfirmationKeyboard
            )
            assert user.status == UserState.INIT_GET_PIN
            assert user.pin != User.PIN_MEMBER_CONFIRMED


# Test handling of INIT_GET_PIN for users who did not have a configured PIN
class TestInitGetPin_PinNotSet(BaseTestClass):

    # Minimal state required
    def _createUser(self, member) -> ndb.Key:
        return self.createUser(
            {
                "status": UserState.INIT_GET_PIN,
                "groupId": TEST_GROUPID,
                "groupName": TEST_GROUPNAME,
                "groupMembers": json.dumps([TEST_MEMBER_NOPIN, TEST_MEMBER_PINSET]),
                "memberId": member["id"],
                "memberName": member["identifier"],
                "pin": User.PIN_MEMBER_CONFIRMED,
            }
        )

    # User has configured a PIN
    def test_hasConfigPin(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(TEST_MEMBER_PINSET)
            update = self.createUpdate(STRINGS["pin_keyboard"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["pin_msg_1"]
            assert user.status == UserState.INIT_CONFIRM_PIN

    # User still has no PIN
    def test_hasNotConfigPin(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(TEST_MEMBER_NOPIN)
            update = self.createUpdate(STRINGS["pin_keyboard"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["set_pin_2"].format(user.groupId)
            assert resp.json()["reply_markup"] == TelegramMarkup.PinConfiguredKeyboard
            assert user.status == UserState.INIT_GET_PIN

    # Tests invalid response (not in keyboard)
    def test_invalidResponse(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser(TEST_MEMBER_NOPIN)
            update = self.createUpdate("invalid response", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["use_keyboard"]
            assert resp.json()["reply_markup"] == TelegramMarkup.PinConfiguredKeyboard
            assert user.status == UserState.INIT_GET_PIN


# Test handling of INIT_CONFIRM_PIN
class TestInitConfirmPin(BaseTestClass):

    # Minimal state required
    def _createUser(self) -> ndb.Key:
        return self.createUser(
            {"status": UserState.INIT_CONFIRM_PIN, "pin": User.PIN_MEMBER_CONFIRMED,}
        )

    # Tests valid PIN
    def test_validPin(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("0000", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["pin_msg_2"].format("0000")
            assert resp.json()["reply_markup"] == TelegramMarkup.PinConfirmationKeyboard
            assert user.pin == "0000"
            assert user.status == UserState.INIT_CONFIRM_PIN_2

    # Tests invalid PIN
    def test_invalidPin(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("PIN0", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["invalid_pin"]
            assert user.pin == User.PIN_MEMBER_CONFIRMED
            assert user.status == UserState.INIT_CONFIRM_PIN


# Test handling of INIT_CONFIRM_PIN_2
class TestInitConfirmPin2(BaseTestClass):

    # Tests PIN confirmed
    def test_pinConfirmed(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_CONFIRM_PIN_2})
            update = self.createUpdate(STRINGS["pin_keyboard_yes"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["setup_summary"].format(
                user.groupName, user.memberName, user.pin
            )
            assert resp.json()["reply_markup"] == TelegramMarkup.SummaryKeyboard
            assert user.status == UserState.INIT_SUMMARY
            assert user.groupMembers == None

    # Tests wrong PIN given
    def test_pinWrong(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_CONFIRM_PIN_2})
            update = self.createUpdate(STRINGS["pin_keyboard_no"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["pin_msg_3"]
            assert user.status == UserState.INIT_GET_PIN

    # Tests invalid response (not in keyboard)
    def test_invalidResponse(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_CONFIRM_PIN_2})
            update = self.createUpdate("invalid response", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["use_keyboard"]
            assert resp.json()["reply_markup"] == TelegramMarkup.PinConfirmationKeyboard
            assert user.status == UserState.INIT_CONFIRM_PIN_2


# Test handling of INIT_SUMMARY:
class TestInitSummary(BaseTestClass):

    # Tests initialization OK
    def test_ok(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_SUMMARY})
            update = self.createUpdate(STRINGS["summary_keyboard_yes"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"].startswith(STRINGS["reminder_not_configured"])
            assert user.status == UserState.REMIND_SET_AM

    # Tests initialization reset
    def test_reset(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_SUMMARY})
            update = self.createUpdate(STRINGS["summary_keyboard_no"], userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["SAF100"]
            assert user.status == UserState.INIT_START

    # Tests invalid response (not in keyboard)
    def test_invalidResponse(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.INIT_SUMMARY})
            update = self.createUpdate("invalid response", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["use_keyboard"]
            assert resp.json()["reply_markup"] == TelegramMarkup.SummaryKeyboard
            assert user.status == UserState.INIT_SUMMARY


# Test handling of REMIND_SET_AM:
class TestRemindSetAm(BaseTestClass):

    # Tests valid AM time sent
    def test_validTime(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.REMIND_SET_AM})
            update = self.createUpdate("11:01", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["reminder_change_config"].format("PM")
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderPmKeyboard
            assert user.status == UserState.REMIND_SET_PM
            assert user.remindAM == 11

    # Tests invalid AM time sent
    def test_invalidTime(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.REMIND_SET_AM})
            update = self.createUpdate("12:01", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["invalid_reminder_time"]
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderAmKeyboard
            assert user.status == UserState.REMIND_SET_AM
            assert user.remindAM == -1


# Test handling of REMIND_SET_PM:
class TestRemindSetPm(BaseTestClass):

    # Tests valid PM time sent
    def test_validTime(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.REMIND_SET_PM})
            update = self.createUpdate("23:01", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["reminder_successful_change"].format(
                f"{user.remindAM:02}:01", f"{user.remindPM:02}:01"
            )
            assert resp.json()["reply_markup"] == TelegramMarkup.FirstSubmitKeyboard
            assert user.status == UserState.TEMP_DEFAULT
            assert user.remindPM == 23

    # Tests invalid PM time sent
    def test_invalidTime(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser({"status": UserState.REMIND_SET_PM})
            update = self.createUpdate("00:01", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["invalid_reminder_time"]
            assert resp.json()["reply_markup"] == TelegramMarkup.ReminderPmKeyboard
            assert user.status == UserState.REMIND_SET_PM
            assert user.remindPM == -1


# Test handling of TEMP_DEFAULT
class TestTempDefault(BaseTestClass):

    # Tests reminder
    def test_reminder(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {"status": UserState.TEMP_DEFAULT, "temp": User.TEMP_NONE}
            )
            update = self.createUpdate("", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert looseCompare(resp.json()["text"], STRINGS["window_open"])
            assert resp.json()["reply_markup"] == TelegramMarkup.TemperatureKeyboard
            assert user.status == UserState.TEMP_REPORT

    # Tests for user that has already submitted
    def test_alreadySubmitted(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {"status": UserState.TEMP_DEFAULT, "temp": "36.0"}
            )
            update = self.createUpdate("", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert "36.0" in resp.json()["text"]
            assert looseCompare(
                resp.json()["text"], STRINGS["already_submitted_AM"]
            ) or looseCompare(resp.json()["text"], STRINGS["already_submitted_PM"])
            assert user.status == UserState.TEMP_DEFAULT


# Test handling of TEMP_REPORT:
class TestTempReport(BaseTestClass):

    # Minimal state required
    def _createUser(self) -> ndb.Key:
        return self.createUser(
            {
                "status": UserState.TEMP_REPORT,
                "groupId": TEST_GROUPID,
                "groupName": TEST_GROUPNAME,
                "memberName": TEST_MEMBER_PINSET["identifier"],
                "memberId": TEST_MEMBER_PINSET["id"],
                "temp": User.TEMP_NONE,
                "pin": "0000",
            }
        )

    # Tests valid temperature sent
    def test_validTemp(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("36.0", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert "36.0" in resp.json()["text"]
            assert looseCompare(resp.json()["text"], STRINGS["just_submitted"])
            assert user.status == UserState.TEMP_DEFAULT
            assert user.temp == "36.0"

    # Tests temperature out of accepted range
    def test_outOfRangeTemp(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("33.0", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["temp_outside_range"]
            assert user.status == UserState.TEMP_REPORT
            assert user.temp == User.TEMP_NONE

    # Test invalid temperature format
    def test_invalidTemp(self):
        with self.ndbClient.context() as context:
            userKey = self._createUser()
            update = self.createUpdate("invalid format", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["invalid_temp"]
            assert user.status == UserState.TEMP_REPORT

    # Test wrong PIN given
    def test_wrongPin(self):
        with self.ndbClient.context() as context:
            userKey = self.createUser(
                {
                    "status": UserState.TEMP_REPORT,
                    "groupId": TEST_GROUPID,
                    "groupName": TEST_GROUPNAME,
                    "memberName": TEST_MEMBER_PINSET["identifier"],
                    "memberId": TEST_MEMBER_PINSET["id"],
                    "temp": User.TEMP_NONE,
                    "pin": "9999",
                }
            )
            update = self.createUpdate("36.0", userKey.id())

            resp = self.sendToWebhook(update)

            context.clear_cache()
            user: User = userKey.get()

            assert resp.json()["text"] == STRINGS["wrong_pin"]
            assert user.status == UserState.WRONG_PIN
            assert user.temp == User.TEMP_ERROR
