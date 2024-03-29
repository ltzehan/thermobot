import logging
import json
from typing import List
from flask import Flask, request, jsonify
from google.cloud import ndb

from .util.telegramWrapper import TelegramApiWrapper

from .stringConstants import StringConstants
from .model.webhookUpdate import WebhookUpdate
from .model.updateHandler import UpdateHandler
from .model.broadcastHandler import BroadcastHandler
from .model.reminderHandler import ReminderHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)-8s :: (%(name)s) > %(message)s"
)


def loadSecrets():
    with open("secrets.json") as ff:
        return json.load(ff)


# Create Flask application
def create_app():

    app = Flask(__name__)
    logger = logging.getLogger(__name__)

    SECRETS = loadSecrets()
    STRINGS = StringConstants().STRINGS
    telegramApi = TelegramApiWrapper(SECRETS["telegram-bot"])

    ndbClient = ndb.Client()

    # Endpoints are placed behind the bot token to limit accessibility
    def getRouteUrl(endpoint):
        botToken = SECRETS["telegram-bot"]
        return f"/{botToken}/{endpoint}"

    # In the production environment, Telegram's API doesn't require a valid response
    # To facilitate testing in development, the response will be either a log string
    # or the payload sent to the Telegram API
    def makeResponse(respObj):
        if app.debug:
            if isinstance(respObj, str):
                return respObj
            else:
                return jsonify(respObj)
        else:
            return "OK"

    #
    #   Define application routes
    #

    # Endpoint for Telegram Bot API webhook
    # In order to facilitate testing, the response wi
    @app.route(getRouteUrl("webhook"), methods=["POST"])
    def webhookRoute():
        try:
            body = request.get_json()
        except:
            logStr = "Received malformed update"
            logging.warning(logStr)
            return makeResponse(logStr)

        # Extract message component from update
        if "message" in body:
            message = body["message"]
        elif "edited_message" in body:
            message = body["edited_message"]
        else:
            # No message component
            return makeResponse("Received update with no message component")

        updateObj = WebhookUpdate(updateId=body["update_id"], messageObj=message)

        if not updateObj.isValid():
            logStr = "Invalid update object"
            logger.warning(logStr)
            return logStr

        with ndbClient.context():
            updateHandler = UpdateHandler(updateObj)
            resp = updateHandler.process()

        telegramApi.sendMessage(resp)

        return makeResponse(resp)

    # Endpoint for Cloud scheduler
    @app.route(getRouteUrl("remind"))
    def remindRoute():

        with ndbClient.context():
            return ReminderHandler.remind(telegramApi)

    # Endpoint for sending broadcasts
    @app.route(getRouteUrl("broadcast"), methods=["POST"])
    def broadcastRoute():

        text = request.get_json()["msg"]

        with ndbClient.context():
            return BroadcastHandler.broadcast(telegramApi, text)

    # Configures bot webhook
    @app.route(getRouteUrl("setWebhook"))
    def setWebhookRoute():
        projectUrl, botToken = SECRETS["project-url"], SECRETS["telegram-bot"]
        url = f"{projectUrl}/{botToken}/webhook"

        resp = telegramApi.setWebhook(url)
        if resp["ok"]:
            return "Set webhook to: " + url
        else:
            return "Failed to set webhook with response: " + str(resp)

    # For testing bot token configuration
    @app.route(getRouteUrl("pingBot"))
    def pingBotRoute():
        resp = telegramApi.getMe()
        return resp["result"]

    return app
