#
#   State Machine for handling users
#

import logging
import json
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
    date: str
    time: str
    dayOfWeek: str


def getFmtNow() -> FmtDateTime:

    # Production and development environment are in different time zones, so we convert all times from UTC manually
    now = datetime.now(timezone.utc) + timedelta(hours=8)

    return FmtDateTime(
        meridies="AM" if now.hour < 12 else "PM",
        date=now.strftime("%d/%m/%Y"),
        time=now.strftime("%H:%M"),
        dayOfWeek=now.strftime("%A"),
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
                # TODO Write tests and check if time is correct
                now = getFmtNow()
                text = STRINGS["window_open"].format(
                    now.time, now.dayOfWeek, now.date, now.meridies
                )

                # Now wait for user to send temperature
                self.user.status = UserState.TEMP_REPORT
                self.user.put()

                return self.update.makeReply(text, TelegramMarkup.TemperatureKeyboard)

            elif command == "/remind":
                # TODO Write tests
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

        # TODO write test
        return self.update.makeReply(STRINGS["invalid_input"])

    def handleByState(self):

        state = self.user.status
        if state == UserState.INIT_START:
            # Get temptaking data
            ttWrapper = TemptakingWrapper(self.update.text)
            if not ttWrapper.isValid():
                return self.update.makeReply(STRINGS["invalid_url"])

            if ttWrapper.load():

                self.user.groupName = ttWrapper.groupName
                self.user.groupId = ttWrapper.groupId
                self.user.groupMembers = json.dumps(ttWrapper.groupMembers)
                self.user.status = UserState.INIT_CONFIRM_URL
                self.user.put()

                return self.update.makeReply(
                    STRINGS["group_msg"].format(ttWrapper.groupName),
                    markup=TelegramMarkup.GroupConfirmationKeyboard,
                )

            else:
                # TODO Check if website is down
                if False:
                    return self.update.makeReply(
                        STRINGS["status_offline_response"], reply=False
                    )
                else:
                    return self.update.makeReply(STRINGS["website_error"], reply=False)

        elif state == UserState.INIT_CONFIRM_URL:
            # User to confirm group URL
            if self.update.text == STRINGS["group_keyboard_yes"]:
                groupMembers: list = json.loads(self.user.groupMembers)
                names = [
                    "{}. <b>{}</b>".format(i, x) for i, x in enumerate(groupMembers)
                ]

                text = STRINGS["member_msg_1"] + "\n".join(names)

                self.user.status = UserState.INIT_GET_NAME
                self.user.put()

                # Maximum lengths imposed by Telegram API
                if len(groupMembers) > 300 or len(text) > 4096:
                    # Request user to manually input their names; too bad for them
                    return self.update.makeReply(
                        STRINGS["member_overflow"].format(str(len(groupMembers)))
                    )

                # Otherwise send a list of names
                return self.update.makeReply(
                    text,
                    TelegramMarkup.NameSelectionKeyboard(
                        [x["identifier"] for x in groupMembers]
                    ),
                    reply=False,
                )

            elif self.update.text == STRINGS["group_keyboard_no"]:
                # User indicated wrong URL
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

        return "TODO"
