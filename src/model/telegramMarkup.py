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
        "keyboard": [["That's right"], ["No it's not"]],
        "one_time_keyboard": True,
    }

