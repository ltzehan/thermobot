class TelegramMarkup:

    # For reporting temperatures
    _temperatureList = [[str(x / 10), str((x + 1) / 10)] for x in range(350, 375, 2)]
    TemperatureKeyboard = {"keyboard": _temperatureList, "one_time_keyboard": True}

