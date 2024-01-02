from datetime import date

from jinja2 import Environment, FileSystemLoader

from src.settings import TEMPLATE_PATH


jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))

jinja_env.filters["double"] = lambda n: n * 2

jinja_env.globals.update({"today": lambda: date.today()})