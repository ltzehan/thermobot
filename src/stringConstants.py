import json

# TODO These are loading on every instantiation, maybe make this a singleton?
class StringConstants:

    STRINGS = None

    def __init__(self):

        if not self.STRINGS:
            with open("strings.json", encoding="utf-8") as ff:
                self.STRINGS = json.load(ff)
