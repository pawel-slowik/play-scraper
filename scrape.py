#!/usr/bin/env python3

import os
import datetime
from typing import Callable, Iterable, Mapping, Tuple, Union

from lxml import html

from browser import create_driver, login, logout, read_balance, read_services
from value_parsers import parse_balance, parse_date, parse_data_cap, parse_quantity
from value_parsers import parse_boolean_state


BalanceValue = Union[str, float, bool, datetime.date]
BalanceParser = Tuple[str, str, Callable]
ServiceParser = Tuple[Tuple[str, bool], str, Callable]


BALANCE_PARSERS: Iterable[BalanceParser] = [
    (
        "Konto",
        "balance_PLN",
        parse_balance,
    ),
    (
        "Data wa\u017cno\u015bci po\u0142\u0105cze\u0144 wychodz\u0105cych",
        "outgoing_expiration_date",
        parse_date,
    ),
    (
        "Data wa\u017cno\u015bci po\u0142\u0105cze\u0144 przychodz\u0105cych",
        "incoming_expiration_date",
        parse_date,
    ),
    (
        "Liczba promocyjnych GB",
        "free_data_GB",
        parse_data_cap,
    ),
    (
        "Limit GB w roamingu UE",
        "cheaper_roaming_EU_data_GB",
        parse_data_cap,
    ),
    (
        "SMS-y do wszystkich",
        "SMS_all_count",
        parse_quantity,
    ),
]


SERVICE_PARSERS: Iterable[ServiceParser] = [
    (
        ("Noce bez limitu", False),
        "no_data_limit_nights",
        parse_boolean_state,
    ),
    (
        ("Noce bez limitu", True),
        "no_data_limit_nights_recurring",
        parse_boolean_state,
    ),
    (
        ("Dzie\u0144 bez limitu w Play Internet na Kart\u0119", False),
        "no_data_limit_day",
        parse_boolean_state,
    ),
    (
        ("Tydzie\u0144 bez limitu GB", False),
        "no_data_limit_week",
        parse_boolean_state,
    ),
    (
        ("Miesi\u0105c bez limitu GB", False),
        "no_data_limit_month",
        parse_boolean_state,
    ),
    (
        ("Miesi\u0105c bez limitu GB", True),
        "no_data_limit_month_recurring",
        parse_boolean_state,
    ),
    (
        ("Ta\u0144sze po\u0142\u0105czenia i smsy na Ukrain\u0119", True),
        "cheaper_UA",
        parse_boolean_state,
    ),
    (
        ("1000 minut na Ukrain\u0119", False),
        "voice_bundle_1000min_UA",
        parse_boolean_state,
    ),
    (
        ("1000 minut na Ukrain\u0119 + 10 GB na Viber", False),
        "voice_bundle_1000min_UA_Viber_10GB",
        parse_boolean_state,
    ),
    (
        ("Pakiet 1000 minut na Ukrain\u0119 i...", False),
        "voice_bundle_1000min_UA_unlimited_PL",
        parse_boolean_state,
    ),
    (
        ("Pakiet 1000 minut na Ukrain\u0119 i...", True),
        "voice_bundle_1000min_UA_unlimited_PL_recurring",
        parse_boolean_state,
    ),
    (
        ("Roaming zagraniczny", False),
        "roaming",
        parse_boolean_state,
    ),
    (
        ("500 MB do wykorzystania w UE", False),
        "roaming_EU_data_bundle_500MB",
        parse_boolean_state,
    ),
    (
        ("1 GB do wykorzystania w UE", False),
        "roaming_EU_data_bundle_1GB",
        parse_boolean_state,
    ),
    (
        ("3 GB do wykorzystania w UE", False),
        "roaming_EU_data_bundle_3GB",
        parse_boolean_state,
    ),
    (
        ("Pakiet Internet Emiraty 150 MB", False),
        "roaming_AE_data_bundle_150MB",
        parse_boolean_state,
    ),
    (
        ("Pakiet Internet \u015awiat 1 GB", False),
        "roaming_data_bundle_1GB",
        parse_boolean_state,
    ),
    (
        ("Pakiet Internet \u015awiat 300 MB", False),
        "roaming_data_bundle_300MB",
        parse_boolean_state,
    ),
    (
        ("29 gr za minut\u0119 do Bangladeszu", False),
        "voice_29_BD",
        parse_boolean_state,
    ),
    (
        ("29 gr za minut\u0119 do Indii", False),
        "voice_29_IN",
        parse_boolean_state,
    ),
    (
        ("70 gr za minut\u0119 do Nepalu", False),
        "voice_29_NP",
        parse_boolean_state,
    ),
    (
        ("Taniej do Bangladeszu", False),
        "cheaper_BD",
        parse_boolean_state,
    ),
    (
        ("Taniej do Indii", False),
        "cheaper_IN",
        parse_boolean_state,
    ),
    (
        ("Taniej do Nepalu", False),
        "cheaper_NP",
        parse_boolean_state,
    ),
    (
        ("Przed\u0142u\u017cenie wa\u017cno\u015bci konta o 7 dni", False),
        "extend_7days",
        parse_boolean_state,
    ),
    (
        ("Przed\u0142u\u017cenie wa\u017cno\u015bci konta o 31 dni", False),
        "extend_31days",
        parse_boolean_state,
    ),
    (
        ("Przed\u0142u\u017cenie wa\u017cno\u015bci konta o 365 dni", False),
        "extend_365days",
        parse_boolean_state,
    ),
]


def parse_balance_data(html_code: str) -> Mapping[str, BalanceValue]:
    row_xpath = (
        "//div[contains(@class, 'border-apla')]"
        "/div[@class='level']"
    )
    label_xpath = "./div[contains(@class, 'level-left')]"
    value_xpath = "./div[contains(@class, 'level-item')]"
    parsed = parse_table(html_code, row_xpath, label_xpath, value_xpath)
    return {
        key: parser(parsed[label])
        for label, key, parser in BALANCE_PARSERS
    }


def parse_services_data(html_code: str) -> Mapping[str, bool]:
    row_xpath = "//div[contains(@class, 'image-tile')]"
    label_xpath = ".//p[contains(@class, 'tile-title')]"
    value_xpath = ".//div[contains(@class, 'active-label')]"
    flag_xpath = ".//div[contains(@class, 'tile-actions')]/div[contains(., 'miesi\u0119cznie')]"
    parsed = parse_flagged_table(
        html_code,
        row_xpath,
        label_xpath,
        value_xpath,
        flag_xpath
    )
    return {
        key: parser(parsed[label])
        for label, key, parser in SERVICE_PARSERS
    }


def parse_table(
        html_code: str,
        row_xpath: str,
        label_xpath: str,
        value_xpath: str,
) -> Mapping[str, str]:
    return {
        xpath_text(row_node, label_xpath, False):
        first_line(xpath_text(row_node, value_xpath, False)).strip()
        for row_node in html.fromstring(html_code).xpath(row_xpath)
    }


def parse_flagged_table(
        html_code: str,
        row_xpath: str,
        label_xpath: str,
        value_xpath: str,
        flag_xpath: str
) -> Mapping[Tuple[str, bool], str]:
    return {
        (xpath_text(row_node, label_xpath, True), bool(row_node.xpath(flag_xpath))):
        first_line(xpath_text(row_node, value_xpath, True)).strip()
        for row_node in html.fromstring(html_code).xpath(row_xpath)
    }


def xpath_text(parent_node: html.HtmlElement, xpath: str, allow_empty: bool) -> str:
    nodes = parent_node.xpath(xpath)
    if not nodes and allow_empty:
        return ""
    return nodes[0].text_content().strip()  # type: ignore


def first_line(string: str) -> str:
    return "" if string == "" else string.splitlines()[0]


def filter_output(
        balance_data: Mapping[str, BalanceValue],
        services_data: Mapping[str, bool],
        keys: Iterable[str]
) -> Tuple[
        Mapping[str, BalanceValue],
        Mapping[str, bool]
]:
    keys = tuple(keys)
    if not keys:
        return balance_data, services_data
    output_balance_data = {}
    output_services_data = {}
    for key in keys:
        if key in balance_data:
            output_balance_data[key] = balance_data[key]
            continue
        if key in services_data:
            output_services_data[key] = services_data[key]
            continue
        raise ValueError("invalid key: %s" % key)
    return output_balance_data, output_services_data


def main() -> None:
    import configparser
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="debug mode - show the browser window instead of making it headless",
    )
    parser.add_argument(
        "-k", "--keep",
        action="store_true",
        help="save downloaded HTML (usefull when testing changed content)",
    )
    args = parser.parse_args()

    config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, "24.play.pl.ini"))

    timeout = config.getint("browser", "timeout", fallback=20)
    driver = create_driver(args.debug)
    login(driver, config.get("auth", "login"), config.get("auth", "password"), timeout)
    balance_html = read_balance(driver, timeout)
    services_html = read_services(driver, timeout)
    if args.keep:
        open("balance.html", "w").write(balance_html)
        open("services.html", "w").write(services_html)
    logout(driver, timeout)
    driver.quit()
    balance_data = parse_balance_data(balance_html)
    services_data = parse_services_data(services_html)
    if config.has_option("cli", "output"):
        balance_data, services_data = filter_output(
            balance_data,
            services_data,
            config.get("cli", "output").split()
        )
    for key, value in balance_data.items():
        print("%s: %s" % (key, value))
    for key, value in services_data.items():
        print("%s: %s" % (key, value))


if __name__ == "__main__":
    main()
