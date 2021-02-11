#!/usr/bin/env python3

import os
import re
import datetime
from time import sleep
from typing import Callable, Iterable, Mapping, Tuple, Union, Match

from lxml import html
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver import Firefox, FirefoxProfile
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support.ui import WebDriverWait


BalanceValue = Union[str, float, bool, datetime.date]


def create_driver() -> WebDriver:
    firefox_options = Options()
    firefox_options.add_argument("-headless")
    # disable navigator.webdriver in order to make driver automation
    # undetectable: https://stackoverflow.com/a/60626696
    profile = FirefoxProfile()
    profile.set_preference("dom.webdriver.enabled", False)
    profile.set_preference("useAutomationExtension", False)
    profile.update_preferences()
    driver = Firefox(
        executable_path="./selenium-drivers/geckodriver",
        options=firefox_options,
        firefox_profile=profile,
    )
    return driver


def login(driver: WebDriver, username: str, password: str, timeout: int) -> None:

    def find_form_username_input(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("input[name=IDToken1]")

    def find_form_password_input(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("input[name=IDToken2]")

    def find_form_submit_button(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("button[name='Login.Submit']")

    def login_form_is_loaded(driver: WebDriver) -> bool:
        return bool(
            find_form_username_input(driver)
            and find_form_password_input(driver)
            and find_form_submit_button(driver)
        )

    def user_profile_is_loaded(driver: WebDriver) -> bool:
        if driver.current_url != "https://24.play.pl/Play24/Welcome":
            return False
        if not find_balance_button(driver):
            return False
        for loader in driver.find_elements_by_css_selector(".loader-content"):
            try:
                if loader.is_displayed():
                    return False
            except StaleElementReferenceException:
                return False
        return True

    wait = WebDriverWait(driver, timeout)
    driver.get("https://24.play.pl/")
    wait.until(login_form_is_loaded)
    find_form_username_input(driver).send_keys(username)
    sleep(2)
    find_form_password_input(driver).send_keys(password)
    sleep(2)
    find_form_submit_button(driver).click()
    wait.until(user_profile_is_loaded)


def read_balance(driver: WebDriver, timeout: int) -> str:

    def find_close_balance_modal_button(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("#fancybox-close")

    def find_balance_modal(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("#ballancesModalBox")

    def balance_modal_is_loaded(driver: WebDriver) -> bool:
        modal = find_balance_modal(driver)
        if not modal:
            return False
        if modal.is_displayed():
            return True
        return False

    wait = WebDriverWait(driver, timeout)
    find_balance_button(driver).click()
    wait.until(balance_modal_is_loaded)
    balance_html: str = find_balance_modal(driver).get_property("innerHTML")
    find_close_balance_modal_button(driver).click()
    wait.until(lambda driver: not balance_modal_is_loaded(driver))
    return balance_html


def find_balance_button(driver: WebDriver) -> WebElement:
    return driver.find_element_by_css_selector("#accountBallances a")


def read_services(driver: WebDriver, timeout: int) -> str:
    services_url = "https://24.play.pl/Play24/Services"

    def services_page_is_loaded(driver: WebDriver) -> bool:
        if driver.current_url != services_url:
            return False
        for loader in driver.find_elements_by_css_selector(".loader-content"):
            try:
                if loader.is_displayed():
                    return False
            except StaleElementReferenceException:
                return False
        return True

    wait = WebDriverWait(driver, timeout)
    driver.get(services_url)
    wait.until(services_page_is_loaded)
    services_element = driver.find_element_by_css_selector(".container.services")
    services_html: str = services_element.get_property("innerHTML")
    return services_html


def logout(driver: WebDriver, timeout: int) -> None:
    wait = WebDriverWait(driver, timeout)
    logout_button = driver.find_element_by_css_selector("#ssoLogout")
    logout_button.click()
    wait.until(lambda driver: "Logowanie" in driver.title)


def parse_balance_data(html_code: str) -> Mapping[str, BalanceValue]:
    row_xpath = (
        "//div[contains(@class, 'border-apla')]"
        "/div[@class='level']"
    )
    label_xpath = "./div[contains(@class, 'level-left')]"
    value_xpath = "./div[contains(@class, 'level-item')]"
    parsed = parse_table(html_code, row_xpath, label_xpath, value_xpath, False)
    parsers: Iterable[Tuple[str, str, Callable]] = [
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
    return {
        key: parser(parsed[label])
        for label, key, parser in parsers
    }


def parse_services_data(html_code: str) -> Mapping[str, bool]:
    row_xpath = "//div[contains(@class, 'image-tile')]"
    label_xpath = ".//p[contains(@class, 'tile-title')]"
    value_xpath = ".//div[contains(@class, 'active-label')]"
    flag_xpath = ".//div[contains(@class, 'tile-actions')]/div[contains(., 'miesi\u0119cznie')]"
    label_map = {
        ("Noce bez limitu", False): "no_data_limit_nights",
        ("Noce bez limitu", True): "no_data_limit_nights_recurring",
        ("Dzie\u0144 bez limitu w Play Internet na Kart\u0119", False): "no_data_limit_day",
        ("Tydzie\u0144 bez limitu GB", False): "no_data_limit_week",
        ("Miesi\u0105c bez limitu GB", False): "no_data_limit_month",
        ("Miesi\u0105c bez limitu GB", True): "no_data_limit_month_recurring",
        ("Ta\u0144sze po\u0142\u0105czenia i smsy na Ukrain\u0119", True): "cheaper_UA",
        ("1000 minut na Ukrain\u0119", False): "voice_bundle_1000min_UA",
        ("1000 minut na Ukrain\u0119 + 10 GB na Viber", False):
            "voice_bundle_1000min_UA_Viber_10GB",
        ("Roaming zagraniczny", False): "roaming",
        ("500 MB do wykorzystania w UE", False): "roaming_EU_data_bundle_500MB",
        ("1 GB do wykorzystania w UE", False): "roaming_EU_data_bundle_1GB",
        ("3 GB do wykorzystania w UE", False): "roaming_EU_data_bundle_3GB",
        ("Pakiet Internet Emiraty 150 MB", False): "roaming_AE_data_bundle_150MB",
        ("Pakiet Internet \u015awiat 1 GB", False): "roaming_data_bundle_1GB",
        ("Pakiet Internet \u015awiat 300 MB", False): "roaming_data_bundle_300MB",
        ("29 gr za minut\u0119 do Bangladeszu", False): "voice_29_BD",
        ("29 gr za minut\u0119 do Indii", False): "voice_29_IN",
        ("70 gr za minut\u0119 do Nepalu", False): "voice_29_NP",
        ("Taniej do Bangladeszu", False): "cheaper_BD",
        ("Taniej do Indii", False): "cheaper_IN",
        ("Taniej do Nepalu", False): "cheaper_NP",
        ("Przed\u0142u\u017cenie wa\u017cno\u015bci konta o 7 dni", False): "extend_7days",
        ("Przed\u0142u\u017cenie wa\u017cno\u015bci konta o 31 dni", False): "extend_31days",
        ("Przed\u0142u\u017cenie wa\u017cno\u015bci konta o 365 dni", False): "extend_365days",
    }
    value_map = {
        "": False,
        "W\u0142\u0105czony": True,
    }
    parsed = parse_flagged_table(
        html_code,
        row_xpath,
        label_xpath,
        value_xpath,
        flag_xpath
    )
    return {label_map[label]: value_map[value] for label, value in parsed.items()}


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


def parse_table(
        html_code: str,
        row_xpath: str,
        label_xpath: str,
        value_xpath: str,
        allow_empty_value: bool
) -> Mapping[str, str]:
    return {
        xpath_text(row_node, label_xpath, False):
        first_line(xpath_text(row_node, value_xpath, allow_empty_value)).strip()
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
    config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, "24.play.pl.ini"))
    timeout = config.getint("browser", "timeout", fallback=20)
    driver = create_driver()
    login(driver, config.get("auth", "login"), config.get("auth", "password"), timeout)
    balance_html = read_balance(driver, timeout)
    services_html = read_services(driver, timeout)
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
