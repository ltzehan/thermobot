#
#   State Machine for handling users
#

import logging
from typing import NamedTuple
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from stringConstants import StringConstants

from model.user import User, UserState
from model.webhookUpdate import WebhookUpdate
from model.telegramMarkup import TelegramMarkup

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
            command = str.strip(self.update.text)
            return self.parseCommand(command)

        else:
            # Pass to state machine
            return self.handleByState()

    def parseCommand(self, command: str):

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

                # Update user state
                self.user.status = UserState.TEMP_REPORT
                self.user.put()

                return self.update.makeReply(text, TelegramMarkup.TemperatureKeyboard)

            elif command == "/remind":
                # Configure reminders
                # TODO
                return "TODO"

        # TODO write test
        return self.update.makeReply(STRINGS["invalid_input"])

    def handleByState(self):
        # TODO
        return "TODO"
