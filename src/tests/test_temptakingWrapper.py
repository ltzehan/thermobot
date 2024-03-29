from ..util.temptakingWrapper import TemptakingWrapper

TEST_URL = "https://temptaking.ado.sg/group/49c22125544196a0ce745f504bd0608a"
TEST_GROUPID = "49c22125544196a0ce745f504bd0608a"
TEST_GROUPNAME = "thermobot-test"

# Test user with no PIN
TEST_MEMBER_NOPIN = {"id": "14770373", "identifier": "thermobot-nopin", "hasPin": False}

# Test user with PIN set
TEST_MEMBER_PINSET = {
    "id": "14717782",
    "identifier": "thermobot-pinset",
    "hasPin": True,
}


class TestTemptakingWrapper:

    # Tests URL matching
    def test_valid(self):
        ttWrapper = TemptakingWrapper("https://temptaking.ado.sg/group/test")
        assert ttWrapper.isValid()
        assert ttWrapper.groupUrl == "https://temptaking.ado.sg/group/test"

        ttWrapper = TemptakingWrapper("http://temptaking.ado.sg/group/test")
        assert ttWrapper.isValid()
        assert ttWrapper.groupUrl == "https://temptaking.ado.sg/group/test"

        ttWrapper = TemptakingWrapper("temptaking.ado.sg/group/test")
        assert ttWrapper.isValid()
        assert ttWrapper.groupUrl == "https://temptaking.ado.sg/group/test"

        assert not TemptakingWrapper("temptaking.ado.sg/group").isValid()

    # Tests loading of website
    def test_load(self):

        ttWrapper = TemptakingWrapper(TEST_URL)
        assert ttWrapper.load()

        assert ttWrapper.groupName == TEST_GROUPNAME
        assert len(ttWrapper.groupMembers) > 0
