#!/usr/bin/env python3

import os
import urllib.parse
import random
import time
import re
import math
import json
import datetime
from abc import ABC, abstractmethod
from typing import Iterable, Mapping, MutableMapping, Tuple, Union, Match
from typing import Optional # pylint: disable-msg=unused-import

import requests
from lxml import html

BalanceValue = Union[str, float, bool, datetime.date]

class Scraper():

    start_url = 'https://24.play.pl/'
    logout_url = 'https://konto.play.pl/opensso/UI/Logout'

    def __init__(self, login: str, password: str) -> None:
        self.login = login
        self.password = password
        self.session = requests.Session()
        self.dwr_id = None # type: Optional[str]

    def log_in(self) -> None:
        # follow a bunch of redirects, picking up cookies along the way,
        # until we land at the login screen
        response = self.session.get(self.start_url)
        response.raise_for_status()
        response = self.follow_js_form_redirection(response)
        # fill and send the login form
        login_form = self.find_login_form(response.content)
        post_data = self.form_inputs_to_post_data(login_form)
        post_data['IDToken1'] = self.login
        post_data['IDToken2'] = self.password
        action = urllib.parse.urljoin(response.url, login_form.action)
        response = self.session.post(action, data=post_data)
        response.raise_for_status()
        self.follow_js_form_redirection(response)

    def get_balance(self) -> Mapping[str, BalanceValue]:
        dwr_method = DWRBalance()
        balance_html = dwr_method.call(self.session, **{"dwr_id": self.init_dwr()})
        return self.parse_balance_data(balance_html)

    def list_services(self) -> Mapping[str, bool]:
        dwr_method = DWRServices()
        services_html = dwr_method.call(self.session, **{"dwr_id": self.init_dwr()})
        return self.parse_services_data(services_html)

    def log_out(self) -> None:
        response = self.session.get(self.logout_url)
        response.raise_for_status()

    def init_dwr(self) -> str:
        if self.dwr_id is not None:
            return self.dwr_id
        dwr_method = DWRInit()
        self.dwr_id = dwr_method.call(self.session)
        self.session.cookies.set( # type: ignore
            dwr_method.cookie_name,
            self.dwr_id,
            domain=dwr_method.cookie_domain
        )
        return self.dwr_id

    def parse_balance_data(self, html_code: str) -> Mapping[str, BalanceValue]:

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

        def parse_hours_minutes(hours_minutes_str: str) -> int:
            match = re.search("^(?P<hours>[0-9]+):(?P<minutes>[0-9]+) min", hours_minutes_str)
            if not match:
                raise ValueError("invalid hours:minutes value: %s" % hours_minutes_str)
            hours = int(match.group("hours"))
            minutes = int(match.group("minutes"))
            if minutes > 59:
                raise ValueError("invalid minutes value: %s" % hours_minutes_str)
            return hours * 60 + minutes

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

        row_xpath = (
            "//div[contains(@class, 'border-apla')]"
            "/div[@class='level']"
        )
        label_xpath = "./div[contains(@class, 'level-left')]"
        value_xpath = "./div[contains(@class, 'level-item')]"
        parsed = self.parse_table(html_code, row_xpath, label_xpath, value_xpath, False)
        label_map = {
            'Konto': 'balance_PLN',
            'Data wa\u017cno\u015bci po\u0142\u0105cze\u0144 wychodz\u0105cych':
                'outgoing_expiration_date',
            'Data wa\u017cno\u015bci po\u0142\u0105cze\u0144 przychodz\u0105cych':
                'incoming_expiration_date',
            'Promocyjny Internet': 'data_sale',
            'Liczba promocyjnych GB': 'free_data_GB',
            'Limit GB w roamingu UE': 'cheaper_roaming_EU_data_GB',
            'Limit wydatk\xf3w na us\u0142ugi Premium': 'premium_services_limit_PLN',
            'Suma do\u0142adowa\u0144 w tym miesi\u0105cu': 'credit_this_month_PLN',
            'Minuty na Ukrain\u0119': 'UA_minutes',
            'Minuty do wszystkich sieci': 'minutes_all_networks',
            'SMS-y do wszystkich': 'SMS_all_count',
        }
        value_parsers = {
            'balance_PLN': parse_balance,
            'outgoing_expiration_date': parse_date,
            'incoming_expiration_date': parse_date,
            'data_sale': lambda x: x,
            'free_data_GB': parse_data_cap,
            'cheaper_roaming_EU_data_GB': parse_data_cap,
            'premium_services_limit_PLN': parse_balance,
            'credit_this_month_PLN': parse_balance,
            'UA_minutes': parse_hours_minutes,
            'minutes_all_networks': parse_hours_minutes,
            'SMS_all_count': parse_quantity,
        }
        return {
            label_map[label]: value_parsers[label_map[label]](value)
            for label, value in parsed.items()
        }

    def parse_services_data(self, html_code: str) -> Mapping[str, bool]:
        row_xpath = "//div[contains(@class, 'image-tile')]"
        label_xpath = ".//p[contains(@class, 'temp_title')]"
        value_xpath = ".//div[contains(@class, 'active-label')]"
        flag_xpath = ".//div[contains(@class, 'tile-actions')]/div[contains(., 'miesi\u0119cznie')]"
        label_map = {
            ('Noce bez limitu', False): 'no_data_limit_nights',
            ('Noce bez limitu', True): 'no_data_limit_nights_recurring',
            ('Dzie\u0144 bez limitu w Play Internet na Kart\u0119', False): 'no_data_limit_day',
            ('Tydzie\u0144 bez limitu GB', False): 'no_data_limit_week',
            ('Miesi\u0105c bez limitu GB', False): 'no_data_limit_month',
            ('Miesi\u0105c bez limitu GB', True): 'no_data_limit_month_recurring',
            ('Ta\u0144sze po\u0142\u0105czenia i smsy na Ukrain\u0119', True): 'cheaper_UA',
            ('1000 minut na Ukrain\u0119', False): 'voice_bundle_1000min_UA',
            ('1000 minut na Ukrain\u0119 + 10 GB na Viber', False):
                'voice_bundle_1000min_UA_Viber_10GB',
            ('Roaming zagraniczny', False): 'roaming',
            ('500 MB do wykorzystania w UE', False): 'roaming_EU_data_bundle_500MB',
            ('1 GB do wykorzystania w UE', False): 'roaming_EU_data_bundle_1GB',
            ('3 GB do wykorzystania w UE', False): 'roaming_EU_data_bundle_3GB',
            ('Pakiet Internet Emiraty 150 MB', False): 'roaming_AE_data_bundle_150MB',
            ('Pakiet Internet \u015awiat 1 GB', False): 'roaming_data_bundle_1GB',
            ('Pakiet Internet \u015awiat 300 MB', False): 'roaming_data_bundle_300MB',
            ('Taniej na Ukrain\u0119', False): '1000min_10GB_UA',
            ('Internet za darmo po do\u0142adowaniu za 20 z\u0142', False): 'free_data_20PLN',
            ('Nawet 200 GB za darmo dla student\xf3w', False): 'free_data_200GB_for_students',
            ('29 gr za minut\u0119 do Bangladeszu', False): 'voice_29_BD',
            ('29 gr za minut\u0119 do Indii', False): 'voice_29_IN',
            ('70 gr za minut\u0119 do Nepalu', False): 'voice_29_NP',
            ('Taniej do Bangladeszu', False): 'cheaper_BD',
            ('Taniej do Indii', False): 'cheaper_IN',
            ('Taniej do Nepalu', False): 'cheaper_NP',
        }
        value_map = {
            '': False,
            'W\u0142\u0105czony': True,
        }
        parsed = self.parse_flagged_table(
            html_code,
            row_xpath,
            label_xpath,
            value_xpath,
            flag_xpath
        )
        return {label_map[label]: value_map[value] for label, value in parsed.items()}

    @staticmethod
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

    @staticmethod
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

    def follow_js_form_redirection(self, response: requests.Response) -> requests.Response:
        form = html.fromstring(response.content).xpath("//form[1]")[0]
        post_data = self.form_inputs_to_post_data(form)
        response = self.session.post(form.action, data=post_data)
        response.raise_for_status()
        return response

    @staticmethod
    def form_inputs_to_post_data(form: html.HtmlElement) -> MutableMapping[str, str]:
        return {i.name: i.value for i in form.xpath(".//input")}

    @staticmethod
    def find_login_form(page_html: bytes) -> html.HtmlElement:

        def form_has_input(form: html.HtmlElement, input_name: str) -> bool:
            return bool(form.xpath(".//input[@name='%s']" % (input_name,)))

        for form in html.fromstring(page_html).xpath("//form"):
            if form_has_input(form, 'IDToken1') and form_has_input(form, 'IDToken2'):
                return form

class DWRMethod(ABC):

    base_url = "https://24.play.pl/Play24/dwr/"
    page = "/Play24/Welcome"
    cookie_name = "DWRSESSIONID"
    cookie_domain = "24.play.pl"
    url = ""

    def call(self, session: requests.Session, **kwargs: str) -> str:
        response = session.post(self.url, self.create_payload(**kwargs).encode("us-ascii"))
        response.raise_for_status()
        return self.parse_response(response.text)

    @classmethod
    def create_url(cls, path: str) -> str:
        return urllib.parse.urljoin(cls.base_url, path)

    @staticmethod
    def params_to_payload(params: Mapping[str, str]) -> str:
        return ''.join(["%s=%s\n" % (p_name, p_value) for p_name, p_value in params.items()])

    @classmethod
    def session_id(cls, dwr_id: str) -> str:
        return '%s/%s-%s' % (
            dwr_id,
            cls.tokenify(int(time.time() * 1000)),
            cls.tokenify(int(random.random() * 1e+16))
        )

    @staticmethod
    def tokenify(number: int) -> str:
        # emulate the JavaScript `dwr.engine.util.tokenify` function
        tokenbuf = []
        charmap = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ*$"
        remainder = number
        while remainder > 0:
            tokenbuf.append(charmap[remainder & 0x3F])
            remainder = math.floor(remainder / 64)
        return ''.join(tokenbuf)

    @abstractmethod
    def create_payload(self, **kwargs: str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def parse_response(response_body: str) -> str:
        pass

class DWRInit(DWRMethod):

    url = DWRMethod.create_url('call/plaincall/__System.generateId.dwr')

    def create_payload(self, **_: str) -> str:
        dwr_init_params = {
            'callCount': '1',
            'c0-scriptName': '__System',
            'c0-methodName': 'generateId',
            'c0-id': '0',
            'batchId': '0',
            'instanceId': '0',
            'page': urllib.parse.quote_plus(self.page),
            'scriptSessionId': '',
        }
        return self.params_to_payload(dwr_init_params)

    @staticmethod
    def parse_response(response_body: str) -> str:
        regexp = r'dwr\.engine\.remote\.handleCallback\("[0-9]+","[0-9]+","([^"]+)"\);'
        match = re.search(regexp, response_body)
        if not match:
            raise ValueError("unparseable init response: %s" % response_body)
        return match.group(1)

class DWRBalance(DWRMethod):

    url = DWRMethod.create_url('call/plaincall/balanceRemoteService.getBalances.dwr')

    def create_payload(self, **kwargs: str) -> str:
        balance_params = {
            'callCount': '1',
            'nextReverseAjaxIndex': '0',
            'c0-scriptName': 'balanceRemoteService',
            'c0-methodName': 'getBalances',
            'c0-id': '0',
            'batchId': '0',
            'instanceId': '0',
            'page': urllib.parse.quote_plus(self.page),
            'scriptSessionId': self.session_id(kwargs["dwr_id"]),
        }
        return self.params_to_payload(balance_params)

    @staticmethod
    def parse_response(response_body: str) -> str:
        begin_marker = re.escape(
            'dwr.engine.remote.handleCallback("0","0",'
            'dwr.engine.remote.newObject("BaseDwrTransferData",'
            '{responseStatus:dwr.engine.remote.newObject("ServiceDwrResponse",'
            '{messages:{},nextStep:null,status:"1"}),tableData:null,view:'
        )
        end_marker = re.escape('}));')
        regexp = r'^%s(.+)%s\s*$' % (begin_marker, end_marker)
        match = re.search(regexp, response_body, re.MULTILINE)
        if not match:
            raise ValueError("unparseable response: %s" % response_body)
        content = json.loads(match.group(1))
        if not isinstance(content, str):
            raise ValueError("unparseable response: %r" % content)
        return content

class DWRServices(DWRMethod):

    url = DWRMethod.create_url('call/plaincall/servicesRemoteService.getComponentsList.dwr')

    def create_payload(self, **kwargs: str) -> str:
        service_params = {
            'callCount': '1',
            'nextReverseAjaxIndex': '0',
            'c0-scriptName': 'servicesRemoteService',
            'c0-methodName': 'getComponentsList',
            'c0-id': '0',
            'c0-param0': 'string:PL24_PACKETS',
            'batchId': '0',
            'instanceId': '0',
            'page': urllib.parse.quote_plus(self.page),
            'scriptSessionId': self.session_id(kwargs["dwr_id"]),
        }
        return self.params_to_payload(service_params)

    @staticmethod
    def parse_response(response_body: str) -> str:
        return DWRBalance.parse_response(response_body)

def xpath_text(parent_node: html.HtmlElement, xpath: str, allow_empty: bool) -> str:
    nodes = parent_node.xpath(xpath)
    if not nodes and allow_empty:
        return ""
    return nodes[0].text_content().strip() # type: ignore

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
    config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    config = configparser.ConfigParser()
    config.read(os.path.join(config_dir, '24.play.pl.ini'))
    scraper = Scraper(config.get('auth', 'login'), config.get('auth', 'password'))
    scraper.log_in()
    balance_data = scraper.get_balance()
    services_data = scraper.list_services()
    scraper.log_out()
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

if __name__ == '__main__':
    main()
