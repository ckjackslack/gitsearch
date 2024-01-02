from falcon.routing import BaseConverter


class CustomConverter(BaseConverter):
    def _validate(self, value):
        if not all(c == "x" for c in value):
            raise Exception
    def convert(self, value):
        try:
            self._validate(value)
            size = len(value)
            return f"{size}x"
        except:
            return None
