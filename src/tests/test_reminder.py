import requests

from .baseTestClass import BaseTestClass

from ..model.user import User
from ..util.fmtDateTime import FmtDateTime


class TestReminder(BaseTestClass):
    def test_reminder(self):
        with self.ndbClient.context():

            now = FmtDateTime.now()
            for _ in range(10):
                self.createUser({"remindPM": now.dateObj.hour, "temp": User.TEMP_NONE})

            url = f"{self.apiUrl}/remind"
            resp = requests.get(url)

            assert resp.status_code == 200

