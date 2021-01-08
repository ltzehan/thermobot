#
#   Helper script for starting up local development server
#   - Attaches webhook to round-robin and reporting bots
#   - Starts flask server
#

import os
import json
import requests
import time
import sys
import threading
from pprint import pprint as pp

# Returns the endpoint URL for a Telegram Bot API method
def getUrl(token, method):
    return "https://api.telegram.org/bot{}/{}".format(token, method)


# Get the internet-facing URL of the ngrok tunnel
# Tunnels are listed on port 4040
def getNgrokUrl():

    # Try 3 times before throwing an error
    attempt = 0

    while attempt <= 3:

        try:
            attempt += 1

            r = requests.get("http://localhost:4040/api/tunnels")
            res = r.json()

            url = res["tunnels"][1]["public_url"]
            return url[url.find("//") + 2 :]

        except Exception as e:

            if attempt >= 3:
                print(e.args)
                print("Failed to detect tunnel. Is ngrok running?")

                exit()

            else:
                # Wait a bit before trying
                time.sleep(1)


def setWebhook(token, baseUrl):

    # Endpoint for the bot
    url = "{}/{}/webhook".format(baseUrl, token)

    r = requests.post(getUrl(token, "setWebhook"), data={"url": url})
    res = r.json()

    if res["ok"]:

        r = requests.get(getUrl(token, "getWebhookInfo"))
        res = r.json()

        print("Successfully set webhook to [{}]".format(res["result"]["url"]))

    else:
        print("Failed to set webhook:")
        pp(res)


if __name__ == "__main__":

    # Loads API tokens from file
    with open("secrets.json", "r") as tf:
        tokens = json.load(tf)

    if len(sys.argv) > 1:
        # Receive ngrok URL as argument
        ngrokUrl = sys.argv[1]
    else:
        # Try to automatically resolve
        ngrokUrl = getNgrokUrl()

    print("ngrok URL: {}".format(ngrokUrl))

    # Set webhook
    setWebhook(tokens["telegram-bot"], ngrokUrl)
