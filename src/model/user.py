#
#   Cloud NDB entity for handling user
#

from google.cloud import ndb

# The string enum values are inherited for back-compatability reasons
class UserState:
    # Initialization states
    INIT_DEFAULT = "0"
    INIT_START = "1"
    INIT_CONFIRM_URL = "2"
    INIT_GET_NAME = "3"
    INIT_CONFIRM_NAME = "4"
    INIT_GET_PIN = "5"
    INIT_CONFIRM_PIN = "6"
    INIT_SUMMARY = "7"

    # Default state after configuration
    TEMP_DEFAULT = "endgame 1"
    # Awaiting user to send temperature
    TEMP_REPORT = "endgame 2"

    # User is configuring reminders
    REMIND_SET_AM = "remind wizard 1"
    REMIND_SET_PM = "remind wizard 2"

    # Error states
    WRONG_PIN = "wrong pin"
    RESUBMIT_TEMP = "resubmit temp"


# Some fields are unused but their logic is maintained for back-compatability
class User(ndb.Model):
    # Currently unused
    firstName = ndb.StringProperty()

    # User state in the state machine
    status = ndb.StringProperty(default=UserState.INIT_DEFAULT)

    # From temptaking website
    groupId = ndb.StringProperty()
    groupName = ndb.StringProperty()
    groupMembers = ndb.TextProperty()

    memberName = ndb.StringProperty()
    memberId = ndb.StringProperty()

    pin = ndb.StringProperty()
    # Set when user confirms their name but have not set a PIN on the website
    PIN_NOTSET = "no pin"

    # Last recorded temperature
    temp = ndb.StringProperty()
    # Reset at the start of a new session
    TEMP_NONE = "none"
    # Temperature wasn't set because of an error
    TEMP_ERROR = "error"

    # Time for reminders
    # Only store the hour since the reminders are sent at the start of the configured hour
    remindAM = ndb.IntegerProperty(default=-1)
    remindPM = ndb.IntegerProperty(default=-1)
    VALID_AM_TIMES = [f"{x:02}:01" for x in range(12)]
    VALID_PM_TIMES = [f"{x:02}:01" for x in range(12, 24)]

    blocked = ndb.BooleanProperty(default=False)

    # To maintain back-compatability with the Cloud Datastore
    @classmethod
    def _get_kind(cls):
        return "Client"

    def reset(self):
        self.status = UserState.INIT_START
        self.groupId = None
        self.groupName = None
        self.groupMembers = None
        self.memberName = None
        self.memberId = None
        self.pin = None
        self.temp = "init"
        self.remindAM = -1
        self.remindPM = -1
        self.blocked = False

    # User can only issue commands after initialization
    def canIssueCommand(self) -> bool:
        return self.status in [
            UserState.TEMP_DEFAULT,
            UserState.TEMP_REPORT,
            UserState.REMIND_SET_AM,
            UserState.REMIND_SET_PM,
            "offline,endgame 1",
            "offline,endgame 2",
            "offline,remind wizard 1",
            "offline,remind wizard 2",
        ]

