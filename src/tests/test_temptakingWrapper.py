from ..temptakingWrapper import TemptakingWrapper

TEST_URL = "https://temptaking.ado.sg/group/45442b0cf7f2cb90783f421805e6ad8d"


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

        # No test group so any one is fine
        assert ttWrapper.groupName == "Adept"
        assert ttWrapper.groupId == "45442b0cf7f2cb90783f421805e6ad8d"
        assert len(ttWrapper.groupMembers) > 0
