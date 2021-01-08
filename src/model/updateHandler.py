#
#   State Machine for handling users
#

import logging
import json
import re
import requests
from typing import NamedTuple
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from ..stringConstants import StringConstants

from .user import User, UserState
from .webhookUpdate import WebhookUpdate
from .telegramMarkup import TelegramMarkup
from ..util.temptakingWrapper import TemptakingWrapper

STRINGS = StringConstants().STRINGS


class FmtDateTime(NamedTuple):
    meridies: str
    shortDate: str
    date: str
    time: str
    dayOfWeek: str
    clockEmoji: str


def getFmtNow() -> FmtDateTime:

    # Production and development environment are in different time zones, so we convert all times from UTC manually
    now = datetime.now(timezone.utc) + timedelta(hours=8)

    clockEmojiIndex = round(2 * (now.hour + now.minute / 60) % 24)

    return FmtDateTime(
        meridies="AM" if now.hour < 12 else "PM",
        shortDate=now.strftime("%d/%m/%y"),
        date=now.strftime("%d/%m/%Y"),
        time=now.strftime("%H:%M"),
        dayOfWeek=now.strftime("%A"),
        clockEmoji=STRINGS["clocks"][clockEmojiIndex],
    )


class UpdateHandler:
    def __init__(self, updateObj: WebhookUpdate):
        self.update = updateObj

    def process(self):

        # Check if update is for a text message (the only valid type recognized)
        if self.update.text is None:
            resp = self.update.makeReply(STRINGS["no_text_error"])

            return resp

        # Get User entity or create a new User if this is the User's first interaction
        # This is strange because we are not querying against a particular entity key
        # but the legacy database has its own PK field which is the user's Telegram user ID
        self.user: User = User.get_or_insert(self.update.chatId)

        if self.update.text.startswith("/"):
            # User issued a command (does not depend on user state)
            return self.handleCommand()
        else:
            # Pass to state machine
            return self.handleByState()

    # Starts the reminder wizard
    def startReminderWizard(self):

        # Configure reminders
        if self.user.remindAM == -1 or self.user.remindPM == -1:
            # Reminder not configured
            text = STRINGS["reminder_not_configured"]
        else:
            # Show existing configuration
            currentAm, currentPm = self.user.remindAM, self.user.remindPM
            text = STRINGS["reminder_existing_config"].format(
                f"{currentAm:02}:01", f"{currentPm:02}:01"
            )

        text += STRINGS["reminder_change_config"].format("AM")

        # Now waiting for user to send AM reminder time
        self.user.status = UserState.REMIND_SET_AM
        self.user.put()

        return self.update.makeReply(text, TelegramMarkup.ReminderAmKeyboard)

    # Handles commands (text starting with "/")
    def handleCommand(self):

        command = str.strip(self.update.text)

        # Only command user can issue before completing initialization
        if command == "/start":
            # Reset user state
            self.user.reset()
            self.user.put()

            return self.update.makeReply(STRINGS["SAF100"], reply=False)

        # User can only issue commands after initialization
        elif self.user.canIssueCommand():

            if command == "/forcesubmit":

                # Override previous temperature for this session
                self.user.temp = User.TEMP_NONE
                self.user.put()

                return self.sendReminder()

            elif command == "/remind":
                return self.startReminderWizard()

        return self.update.makeReply(STRINGS["invalid_input"])

    # Checks if error is caused by temptaking website being offline
    def handleTemptakingError(self):
        # TODO Check if website is down
        if False:
            return self.update.makeReply(
                STRINGS["status_offline_response"], reply=False
            )
        else:
            return self.update.makeReply(STRINGS["website_error"], reply=False)

    # Parses the scraped data of group members and sends a reply asking the user to select their name
    def queryMemberName(self):
        groupMembers: list = json.loads(self.user.groupMembers)
        names = [
            "{}. <b>{}</b>".format(i + 1, x["identifier"])
            for i, x in enumerate(groupMembers)
        ]

        text = STRINGS["member_msg_1"] + "\n".join(names)

        # Maximum lengths imposed by Telegram API
        if len(groupMembers) > 300 or len(text) > 4096:
            # Request user to manually input their names; too bad for them
            return self.update.makeReply(
                STRINGS["member_overflow"].format(str(len(groupMembers))), reply=False
            )

        # Otherwise send a list of names
        return self.update.makeReply(
            text,
            TelegramMarkup.NameSelectionKeyboard(
                [[x["identifier"]] for x in groupMembers]
            ),
            reply=False,
        )

    # Sends reminder to submit temperature
    def sendReminder(self):

        now = getFmtNow()

        if self.user.temp == User.TEMP_NONE:
            # Not yet submitted
            text = STRINGS["window_open"].format(
                now.time, now.dayOfWeek, now.shortDate, now.meridies
            )

            self.user.status = UserState.TEMP_REPORT
            self.user.put()

            return self.update.makeReply(
                text, TelegramMarkup.TemperatureKeyboard, reply=False
            )

        else:
            if now.meridies == "AM":
                text = (
                    STRINGS["already_submitted_AM"].format(
                        now.dayOfWeek, now.shortDate, self.user.temp
                    )
                    + STRINGS["old_user"]
                )
                return self.update.makeReply(text, reply=False)
            else:
                text = (
                    STRINGS["already_submitted_PM"].format(
                        now.dayOfWeek, now.shortDate, self.user.temp
                    )
                    + STRINGS["old_user"]
                )
                return self.update.makeReply(text, reply=False)

    # Submits temperature to temptaking website and returns status
    def submitTemp(self, temp):

        now = getFmtNow()
        try:
            url = TemptakingWrapper.BASE_URL + "MemberSubmitTemperature"
            payload = {
                "groupCode": self.user.groupId,
                "date": now.date,
                "meridies": now.meridies,
                "memberId": self.user.memberId,
                "temperature": temp,
                "pin": self.user.pin,
            }

            resp = requests.post(url, data=payload)
            logger.debug("Temperature submission returned: {}".format(resp.text))

        except Exception as e:

            logger.error(e)
            return "error"

        return resp.text

    def handleByState(self):

        state = self.user.status

        # Get temptaking data
        if state == UserState.INIT_START:

            ttWrapper = TemptakingWrapper(self.update.text)
            if not ttWrapper.isValid():
                return self.update.makeReply(STRINGS["invalid_url"])

            if ttWrapper.load():

                self.user.groupName = ttWrapper.groupName
                self.user.groupId = ttWrapper.groupId
                self.user.groupMembers = json.dumps(ttWrapper.groupMembers)
                self.user.status = UserState.INIT_CONFIRM_URL
                self.user.temp = User.TEMP_NONE
                self.user.put()

                return self.update.makeReply(
                    STRINGS["group_msg"].format(ttWrapper.groupName),
                    markup=TelegramMarkup.GroupConfirmationKeyboard,
                )

            else:
                return self.handleTemptakingError()

        # User to confirm group URL
        elif state == UserState.INIT_CONFIRM_URL:

            if self.update.text == STRINGS["group_keyboard_yes"]:

                self.user.status = UserState.INIT_GET_NAME
                self.user.put()

                return self.queryMemberName()

            # User indicated wrong URL
            elif self.update.text == STRINGS["group_keyboard_no"]:
                # Reset user to previous state to reenter group URL
                self.user.reset()
                self.user.status = UserState.INIT_START
                self.user.put()

                return self.update.makeReply(STRINGS["SAF100_2"], reply=False)

            else:
                return self.update.makeReply(
                    STRINGS["use_keyboard"],
                    TelegramMarkup.GroupConfirmationKeyboard,
                    reply=False,
                )

        # User to enter their name
        elif state == UserState.INIT_GET_NAME:

            groupMembers = json.loads(self.user.groupMembers)

            try:
                # Find index of user's name
                idx = [x["identifier"] for x in groupMembers].index(self.update.text)

                self.user.status = UserState.INIT_CONFIRM_NAME

            except ValueError:
                # TODO Have to handle the two diff cases of normal (user keyboard) and overflow (ask to type)
                return self.update.makeReply(
                    STRINGS["member_invalid"].format(self.update.text)
                )

            self.user.memberId = groupMembers[idx]["id"]
            self.user.memberName = groupMembers[idx]["identifier"]
            self.user.pin = str(groupMembers[idx]["hasPin"])
            self.user.put()

            text = STRINGS["member_msg_2"].format(self.user.memberName)
            return self.update.makeReply(
                text, markup=TelegramMarkup.MemberConfirmationKeyboard, reply=False
            )

        # User to confirm name
        elif state == UserState.INIT_CONFIRM_NAME:

            # User has previously confirmed member name and is returning to set PIN
            if self.user.pin == User.PIN_NOTSET:

                groupUrl = TemptakingWrapper.BASE_URL + self.user.groupId
                ttWrapper = TemptakingWrapper(groupUrl)

                if ttWrapper.load():

                    groupMembers = ttWrapper.groupMembers
                    try:
                        idx = [x["identifier"] for x in groupMembers].index(
                            self.user.memberName
                        )

                        # User has a configured PIN now
                        if groupMembers[idx]["hasPin"]:
                            self.user.status = UserState.INIT_GET_PIN
                            self.user.pin = None
                            self.user.put()

                            return self.update.makeReply(
                                STRINGS["pin_msg_1"], reply=False
                            )

                        # User is a liar
                        else:
                            text = STRINGS["set_pin_2"].format(self.user.groupId)
                            return self.update.makeReply(
                                text,
                                markup=TelegramMarkup.PinConfiguredKeyboard,
                                reply=False,
                            )

                    except ValueError:
                        # User has somehow ceased to exist
                        # This could be a result of user changing groups or their member names
                        # and is easier to just start from a blank slate
                        self.user.reset()
                        self.user.put()

                        return self.update.makeReply(
                            STRINGS["fatal_error"], reply=False
                        )

                else:
                    return self.handleTemptakingError()

            # Otherwise user has not yet confirmed their name
            if self.update.text == STRINGS["member_keyboard_no"]:
                # Ask again
                self.user.status = UserState.INIT_GET_NAME
                self.user.memberName = None
                self.user.put()

                return self.queryMemberName()

            elif self.update.text == STRINGS["member_keyboard_yes"]:

                if self.user.pin == "True":
                    # User has already set a PIN on the website
                    self.user.status = UserState.INIT_GET_PIN
                    self.user.groupMembers = None
                    self.user.put()

                    return self.update.makeReply(STRINGS["pin_msg_1"], reply=False)

                else:
                    # Request user to set PIN first
                    text = STRINGS["set_pin_1"].format(self.user.groupId)

                    self.user.pin = User.PIN_NOTSET
                    self.user.put()

                    return self.update.makeReply(
                        text, markup=TelegramMarkup.PinConfiguredKeyboard, reply=False
                    )

            else:
                return self.update.makeReply(
                    STRINGS["use_keyboard"],
                    markup=TelegramMarkup.MemberConfirmationKeyboard,
                    reply=False,
                )

        # User to enter PIN
        elif state == UserState.INIT_GET_PIN:

            matches = re.findall(r"^\d{4}$", str.strip(self.update.text))

            # Valid PIN
            if len(matches) > 0:

                pin = matches[0]
                text = STRINGS["pin_msg_2"].format(pin)

                self.user.status = UserState.INIT_CONFIRM_PIN
                self.user.pin = pin
                self.user.put()

                return self.update.makeReply(
                    text, markup=TelegramMarkup.PinConfirmationKeyboard, reply=False
                )

            else:
                return self.update.makeReply(STRINGS["invalid_pin"])

        # User to confirm PIN
        elif state == UserState.INIT_CONFIRM_PIN:

            # User confirms correct PIN
            if self.update.text == STRINGS["pin_keyboard_yes"]:

                text = STRINGS["setup_summary"].format(
                    self.user.groupName, self.user.memberName, self.user.pin
                )

                self.user.status = UserState.INIT_SUMMARY
                self.user.put()

                # TODO notify admins

                return self.update.makeReply(
                    text, markup=TelegramMarkup.SummaryKeyboard, reply=False
                )

            elif self.update.text == STRINGS["pin_keyboard_no"]:
                # Ask for PIN again
                self.user.status = UserState.INIT_GET_PIN
                self.user.pin = None
                self.user.put()

                return self.update.makeReply(STRINGS["pin_msg_1"], reply=False)

            else:
                return self.update.makeReply(
                    STRINGS["use_keyboard"],
                    markup=TelegramMarkup.PinConfirmationKeyboard,
                )

        # User to confirm summary of initialization
        elif state == UserState.INIT_SUMMARY:

            # Incorrect details
            if self.update.text == STRINGS["summary_keyboard_no"]:

                # Reset state right to the beginning
                self.user.reset()
                self.user.put()

                return self.update.makeReply(STRINGS["SAF100"], reply=False)

            elif self.update.text == STRINGS["summary_keyboard_yes"]:

                return self.startReminderWizard()

            # Invalid response
            else:
                return self.update.makeReply(
                    STRINGS["use_keyboard"], markup=TelegramMarkup.SummaryKeyboard,
                )

        # User configuring AM reminder
        elif state == UserState.REMIND_SET_AM:

            if self.update.text not in User.VALID_AM_TIMES:
                # Invalid time
                return self.update.makeReply(
                    STRINGS["invalid_reminder_time"],
                    markup=TelegramMarkup.ReminderAmKeyboard,
                )

            else:
                self.user.remindAM = int(self.update.text[:2])
                self.user.status = UserState.REMIND_SET_PM
                self.user.put()

                text = STRINGS["reminder_change_config"].format("PM")
                return self.update.makeReply(
                    text, markup=TelegramMarkup.ReminderPmKeyboard, reply=False
                )

        # User configuring PM reminder
        elif state == UserState.REMIND_SET_PM:

            if self.update.text not in User.VALID_PM_TIMES:
                # Invalid time
                return self.update.makeReply(
                    STRINGS["invalid_reminder_time"],
                    markup=TelegramMarkup.ReminderPmKeyboard,
                )

            else:
                self.user.remindPM = int(self.update.text[:2])
                self.user.status = UserState.TEMP_DEFAULT
                self.user.put()

                text = STRINGS["reminder_successful_change"].format(
                    f"{self.user.remindAM:02}:01", f"{self.user.remindPM:02}:01"
                )

                # Keyboard is just there to prompt user to send another message to trigger next state
                return self.update.makeReply(
                    text, markup=TelegramMarkup.FirstSubmitKeyboard, reply=False
                )

        # User is waiting for reminder
        elif state == UserState.TEMP_DEFAULT:

            return self.sendReminder()

        # User to report temperature
        elif state == UserState.TEMP_REPORT:

            matches = re.findall(r"^\d{2}\.\d", self.update.text)

            # Invalid temperature
            if len(matches) == 0:
                return self.update.makeReply(
                    STRINGS["invalid_temp"],
                    markup=TelegramMarkup.TemperatureKeyboard,
                    reply=False,
                )

            # Temperature is in valid format
            temp = float(self.update.text)

            # Temperature range imposed by temptaking website
            if temp > 40 or temp < 35:
                # User is possibly on the brink of death
                return self.update.makeReply(
                    STRINGS["temp_outside_range"],
                    markup=TelegramMarkup.TemperatureKeyboard,
                    reply=False,
                )

            else:

                resp = self.submitTemp(temp)
                if resp == "OK":

                    now = getFmtNow()
                    text = STRINGS["just_submitted"].format(
                        now.dayOfWeek,
                        now.shortDate,
                        now.meridies,
                        now.clockEmoji,
                        now.time,
                        temp,
                    )

                    self.user.status = UserState.TEMP_DEFAULT
                    self.user.temp = str(temp)
                    self.user.put()

                    return self.update.makeReply(text, reply=False)

                elif resp == "Wrong pin.":

                    self.user.status = UserState.WRONG_PIN
                    self.user.temp = User.TEMP_ERROR
                    self.user.put()

                    return self.update.makeReply(STRINGS["wrong_pin"], reply=False)

                else:
                    # TODO check website status
                    pass

        return self.update.makeReply("TODO")
