import re
import json
import requests
import logging

logger = logging.getLogger(__name__)


class TemptakingWrapper:

    URL_PATTERN = r"temptaking\.ado\.sg/group/.*"

    def __init__(self, groupUrl: str):
        self._isValid = False

        # Check if URL matches the temptaking website URL
        matches = re.findall(self.URL_PATTERN, groupUrl)
        if len(matches) > 0:
            self.groupUrl = f"https://{matches[0]}"
            self._isValid = True

        else:
            logger.info(f"Received invalid URL: {groupUrl}")

    def isValid(self):
        return self._isValid

    def load(self) -> bool:

        if not self.isValid():
            return False

        try:
            resp = requests.get(self.groupUrl)
            html = resp.content.decode("utf-8")
        except:
            logger.warning(
                f"Failed to load temptaking website from url: {self.groupUrl}"
            )
            return False

        if "Invalid code" in html:
            # Not a valid group URL
            logger.warning(f"Temptaking URL {self.groupUrl} is not a valid group")
            return False

        # We don't have an actual endpoint so just scrape data from their script tag
        start = html.find("loadContents") + 14
        end = html.rfind("}") + 1
        groupData = json.loads(html[start:end])

        if start == -1 or end == -1:
            logger.warning(f"Failed to scrape group data from {self.groupUrl}")
            return False

        self.groupName: str = groupData["groupName"]
        self.groupId: str = groupData["groupCode"]
        self.groupMembers = groupData["members"]

        return True

