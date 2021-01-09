import random

from .baseTestClass import BaseTestClass

from ..model.user import User


class TestBroadcast(BaseTestClass):

    # (At least a hundred)
    def test_hundredUsers(self):
        with self.ndbClient.context():

            num = 100 - User.query().count()
            if num > 0:
                for _ in range(num):
                    uid = str(random.randint(0, 1e10))
                    User(id=uid).put_async()

            resp = self.sendToBase("broadcast", {"msg": "Test broadcast"})

