#
#   Wrapper for Telegram Webhook update object
#

from .telegramMarkup import TelegramMarkup


class WebhookUpdate:
    def __init__(self, updateId, messageObj):
        # Not explicitly used but could be useful
        self.id = updateId

        self._isValid = True
        try:
            self.text: str = messageObj.get("text")
            self.messageId: str = messageObj["message_id"]
            self.date: str = messageObj["date"]
            self.fromUserId: str = messageObj["from"]
            self.chatId: str = messageObj["chat"]["id"]
        except:
            # Some field is empty
            self._isValid = False

    def isValid(self):
        return self._isValid

    # Creates a payload for responding to this update
    # By default, the message will be a reply to this update
    def makeReply(self, text: str, markup: TelegramMarkup = None, reply=True):
        payload = {
            "chat_id": str(self.chatId),
            "text": text,
            "parse_mode": "HTML",
        }
        if markup:
            payload["reply_markup"] = markup
        if reply:
            payload["reply_to_message_id"] = str(self.messageId)

        return payload
