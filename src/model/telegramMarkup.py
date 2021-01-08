from ..stringConstants import StringConstants

STRINGS = StringConstants().STRINGS


class TelegramMarkup:

    # For reporting temperatures
    _temperatureList = [[str(x / 10), str((x + 1) / 10)] for x in range(350, 375, 2)]
    TemperatureKeyboard = {"keyboard": _temperatureList, "one_time_keyboard": True}

    # For configuring reminders
    _hourListAm = [[f"{2 * x:02}:01", f"{2 * x + 1:02}:01"] for x in range(6)]
    _hourListPm = [[f"{2 * x:02}:01", f"{2 * x + 1:02}:01"] for x in range(6, 12)]
    ReminderAmKeyboard = {"keyboard": _hourListAm, "one_time_keyboard": True}
    ReminderPmKeyboard = {"keyboard": _hourListPm, "one_time_keyboard": True}

    GroupConfirmationKeyboard = {
        "keyboard": [[STRINGS["group_keyboard_yes"]], [STRINGS["group_keyboard_no"]]],
        "one_time_keyboard": True,
    }

    MemberConfirmationKeyboard = {
        "keyboard": [[STRINGS["member_keyboard_yes"]], [STRINGS["member_keyboard_no"]]],
        "one_time_keyboard": True,
    }

    PinConfiguredKeyboard = {
        "keyboard": [[STRINGS["pin_keyboard"]]],
        "one_time_keyboard": True,
    }

    PinConfirmationKeyboard = {
        "keyboard": [[STRINGS["pin_keyboard_yes"]], [STRINGS["pin_keyboard_no"]],],
        "one_time_keyboard": True,
    }

    SummaryKeyboard = {
        "keyboard": [
            [STRINGS["summary_keyboard_yes"]],
            [STRINGS["summary_keyboard_no"]],
        ],
        "one_time_keyboard": True,
    }

    FirstSubmitKeyboard = {
        "keyboard": [[STRINGS["first_submit"]]],
        "one_time_keyboard": True,
    }

    @classmethod
    def NameSelectionKeyboard(cls, names: list):
        return {
            "keyboard": names,
            "one_time_keyboard": True,
        }
