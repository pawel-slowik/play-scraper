import re
import datetime
from typing import Match


def parse_balance(balance_str: str) -> float:
    match = re.search("^(?P<int>[0-9]+)(,(?P<fract>[0-9]{2})){0,1} z\u0142", balance_str)
    if not match:
        raise ValueError("invalid balance: %s" % balance_str)
    return parse_float(match)


def parse_date(date_str: str) -> datetime.date:
    return datetime.datetime.strptime(date_str, "%d.%m.%Y").date()


def parse_data_cap(cap_str: str) -> float:
    match = re.search("^(?P<int>[0-9]+)(,(?P<fract>[0-9]+)){0,1} (?P<unit>GB|MB)", cap_str)
    if not match:
        raise ValueError("invalid data cap: %s" % cap_str)
    value = parse_float(match)
    if match.group("unit") == "MB":
        value /= 1000
    return value


def parse_quantity(quantity_str: str) -> int:
    match = re.search(r"^(?P<int>[0-9]+) (?P<unit>szt\.)", quantity_str)
    if not match:
        raise ValueError("invalid quantity: %s" % quantity_str)
    return int(match.group("int"))


def parse_float(re_match: Match) -> float:
    value = float(re_match.group("int"))
    if re_match.group("fract") is not None:
        value += float("." + re_match.group("fract"))
    return value


def parse_boolean_state(state: str) -> bool:
    value_map = {
        "": False,
        "W\u0142\u0105czony": True,
    }
    return value_map[state]
