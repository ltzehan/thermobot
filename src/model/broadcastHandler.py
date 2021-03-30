import asyncio
import logging
from time import time
from gevent.pool import Group

logger = logging.getLogger(__name__)

from ..model.user import User
from ..util.telegramWrapper import TelegramApiWrapper


class BroadcastHandler:
    @classmethod
    def broadcast(cls, telegramApi: TelegramApiWrapper, text: str) -> str:

        # Fetch users that aren't blocked
        allUserKeys = User.query(User.blocked == False).fetch(keys_only=True)
        # If the User keys are passed in, the gevent coroutines will be sharing the same
        # NDB context and conflict
        allUserIds = [x.id() for x in allUserKeys]

        SUCCESS = 0
        FAILED = 1
        BLOCKED = -1

        def sendMessage(chatId):

            # Create message payload
            payload = {
                "chat_id": str(chatId),
                "text": text,
                "parse_mode": "HTML",
            }

            try:
                resp = telegramApi.sendMessage(payload)

                if resp["ok"]:
                    return (chatId, SUCCESS)
                else:
                    if resp["error_code"] == 403:
                        # User blocked bot
                        return (chatId, BLOCKED)
                    else:
                        return (chatId, FAILED)
                        logger.error(resp["description"])

            except Exception as e:
                logger.error(e)
                return (chatId, FAILED)

        logger.info("Starting broadcast")

        start = time()

        pool = Group()
        respList = pool.imap_unordered(sendMessage, allUserIds, maxsize=100)

        # Count statuses of broadcast
        success, failed, blocked = 0, 0, 0
        blockedUsers = []
        for resp in respList:
            if resp[1] == SUCCESS:
                success += 1
            elif resp[1] == FAILED:
                failed += 1
            elif resp[1] == BLOCKED:
                blocked += 1
                # TODO Set user status to blocked
                blockedUsers.append(resp[0])

        elapsedTime = time() - start
        rate = len(allUserKeys) / elapsedTime

        logStr = f"Broadcast sent to {len(allUserKeys)} clients in {elapsedTime:.4f}s ({rate:.2f}/s). Successes: {success}, blocked: {blocked}, failures: {failed}"

        logger.info(logStr)
        return logStr
