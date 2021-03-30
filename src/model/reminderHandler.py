import asyncio
import logging
from time import time
from gevent.pool import Group
from google.cloud import ndb

logger = logging.getLogger(__name__)

from ..stringConstants import StringConstants

from ..model.user import User, UserState
from ..model.telegramMarkup import TelegramMarkup
from ..util.telegramWrapper import TelegramApiWrapper
from ..util.fmtDateTime import FmtDateTime

STRINGS = StringConstants().STRINGS


class ReminderHandler:

    ndbClient = ndb.Client()

    @classmethod
    def remind(cls, telegramApi: TelegramApiWrapper) -> str:

        now = FmtDateTime.now()
        hour = now.dateObj.hour

        # TODO reset user temp

        # Fetch users that aren't blocked and have reminders set
        if now.meridies == "AM":
            allUserKeys = User.query(
                User.blocked == False, User.remindAM == hour, User.temp == "none"
            ).fetch(keys_only=True)

        else:
            allUserKeys = User.query(
                User.blocked == False, User.remindPM == hour, User.temp == "none"
            ).fetch(keys_only=True)

        text = STRINGS["window_open"].format(
            now.time, now.dayOfWeek, now.shortDate, now.meridies
        )

        SUCCESS = 0
        FAILED = 1
        BLOCKED = -1

        def sendMessage(userKey: ndb.Key):

            # gevent somehow messes with the ndb context even though it's the same thread
            with cls.ndbClient.context():
                # Create message payload
                payload = {
                    "chat_id": str(userKey.id()),
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": TelegramMarkup.TemperatureKeyboard,
                }

                user: User = userKey.get()

                try:
                    resp = telegramApi.sendMessage(payload)

                    # User statuses have to be updated right after sending or user may hit an invalid state
                    # when they report their temperature
                    if resp["ok"]:
                        user.temp = User.TEMP_NONE
                        user.status = UserState.TEMP_REPORT
                        user.put()

                        return SUCCESS

                    else:
                        if (
                            resp["description"]
                            == "Forbidden: bot was blocked by the user"
                        ):

                            user.reset()
                            user.blocked = True
                            user.put()

                            return BLOCKED
                        else:
                            return FAILED
                            logger.error(resp["description"])

                except Exception as e:
                    logger.error(e)
                    return FAILED

        start = time()

        pool = Group()
        respList = pool.imap_unordered(sendMessage, allUserKeys, maxsize=100)

        # Count statuses of reminder
        success, failed, blocked = 0, 0, 0
        for resp in respList:
            if resp == SUCCESS:
                success += 1
            elif resp == FAILED:
                failed += 1
            elif resp == BLOCKED:
                blocked += 1

        elapsedTime = time() - start
        rate = len(allUserKeys) / elapsedTime

        logStr = f"Reminder sent to {len(allUserKeys)} clients in {elapsedTime:.4f}s ({rate:.2f}/s). Successes: {success}, blocked: {blocked}, failures: {failed}"

        logger.info(logStr)
        return logStr
