#!/usr/bin/env python3

import os
import urllib.parse
import random
import time
import re
import math
import json
import datetime
from typing import Dict, Tuple, Union, Match

import requests
from lxml import html

BalanceValue = Union[str, float, bool, datetime.date]

class Scraper():

    def __init__(self, login: str, password: str) -> None:
        self.login = login
        self.password = password
        self.start_url = 'https://24.play.pl/'
        self.logout_url = 'https://konto.play.pl/opensso/UI/Logout'
        self.session = requests.Session()
        self.dwr: DWR = None
        self.dwr_id: str = None

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

    def get_balance(self) -> Dict[str, BalanceValue]:
        self.init_dwr()
        response = self.session.post(
            self.dwr.balance_url,
            self.dwr.create_balance_payload(self.dwr_id)
        )
        response.raise_for_status()
        balance_html = self.dwr.parse_balance_response(response.text)
        return self.parse_balance_data(balance_html)

    def list_services(self) -> Dict[str, bool]:
        self.init_dwr()
        response = self.session.post(
            self.dwr.services_url,
            self.dwr.create_services_payload(self.dwr_id)
        )
        response.raise_for_status()
        services_html = self.dwr.parse_services_response(response.text)
        return self.parse_services_data(services_html)

    def log_out(self) -> None:
        response = self.session.get(self.logout_url)
        response.raise_for_status()

    def init_dwr(self) -> None:
        if self.dwr is not None:
            return
        # emulate the AJAX end of a Java DWR bridge
        self.dwr = DWR('https://24.play.pl/Play24/dwr/', '/Play24/Welcome')
        response = self.session.post(self.dwr.init_url, self.dwr.create_init_payload())
        response.raise_for_status()
        self.dwr_id = self.dwr.parse_init_response(response.text)
        self.session.cookies.set('DWRSESSIONID', self.dwr_id, domain='24.play.pl')

    def parse_balance_data(self, html_code: str) -> Dict[str, BalanceValue]:

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

        def parse_float(re_match: Match) -> float:
            value = float(re_match.group("int"))
            if re_match.group("fract") is not None:
                value += float("." + re_match.group("fract"))
            return value

        row_xpath = (
            "//div[contains(@class, 'row-fluid')]"
            "/div[contains(@class, 'row-fluid') and not(contains(@class, 'collapse'))]"
        )
        label_xpath = "./span[contains(@class, 'span4')]"
        value_xpath = "./span[contains(@class, 'span5')]"
        parsed = self.parse_table(html_code, row_xpath, label_xpath, value_xpath, False)
        label_map = {
            'Konto': 'balance_PLN',
            'Data wa\u017cno\u015bci po\u0142\u0105cze\u0144 wychodz\u0105cych': 'outgoing_expiration_date',
            'Data wa\u017cno\u015bci po\u0142\u0105cze\u0144 przychodz\u0105cych': 'incoming_expiration_date',
            'Promocyjny Internet': 'data_sale',
            'Liczba promocyjnych GB': 'free_data_GB',
            'Limit GB w roamingu UE': 'cheaper_roaming_EU_data_GB',
            'Limit wydatk\xf3w na us\u0142ugi Premium': 'premium_services_limit_PLN',
        }
        value_parsers = {
            'balance_PLN': parse_balance,
            'outgoing_expiration_date': parse_date,
            'incoming_expiration_date': parse_date,
            'data_sale': lambda x: x,
            'free_data_GB': parse_data_cap,
            'cheaper_roaming_EU_data_GB': parse_data_cap,
            'premium_services_limit_PLN': parse_balance,
        }
        return {
            label_map[label]: value_parsers[label_map[label]](value)
            for label, value in parsed.items()
        }

    def parse_services_data(self, html_code: str) -> Dict[str, bool]:
        row_xpath = "//div[contains(@class, 'ml-8')]"
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
            ('Pakiet 5 GB', False): 'data_bundle_5GB',
            ('Ta\u0144sze po\u0142\u0105czenia i smsy na Ukrain\u0119', True): 'cheaper_UA',
            ('1000 minut na Ukrain\u0119', False): 'voice_bundle_1000min_UA',
            ('Roaming zagraniczny', False): 'roaming',
            ('Paczka roaming internet UE 500 MB', False): 'roaming_EU_data_bundle_500MB',
        }
        value_map = {
            '': False,
            'W\u0142\u0105czony': True,
        }
        parsed = self.parse_flagged_table(html_code, row_xpath, label_xpath, value_xpath, flag_xpath)
        return {label_map[label]: value_map[value] for label, value in parsed.items()}

    @staticmethod
    def parse_table(html_code: str, row_xpath: str, label_xpath: str, value_xpath: str, allow_empty_value: bool) -> Dict[str, str]:

        return {
            xpath_text(row_node, label_xpath, False):
            first_line(xpath_text(row_node, value_xpath, allow_empty_value)).strip()
            for row_node in html.fromstring(html_code).xpath(row_xpath)
        }

    @staticmethod
    def parse_flagged_table(html_code: str, row_xpath: str, label_xpath: str, value_xpath: str, flag_xpath: str) -> Dict[Tuple[str, bool], str]:

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
    def form_inputs_to_post_data(form: html.HtmlElement) -> Dict[str, str]:
        return {i.name: i.value for i in form.xpath(".//input")}

    @staticmethod
    def find_login_form(page_html: bytes) -> html.HtmlElement:

        def form_has_input(form: html.HtmlElement, input_name: str) -> bool:
            return bool(form.xpath(".//input[@name='%s']" % (input_name,)))

        for form in html.fromstring(page_html).xpath("//form"):
            if form_has_input(form, 'IDToken1') and form_has_input(form, 'IDToken2'):
                return form

class DWR():

    def __init__(self, base_url: str, page: str) -> None:
        self.base_url = base_url
        self.page = page
        self.init_url = urllib.parse.urljoin(
            self.base_url,
            'call/plaincall/__System.generateId.dwr'
        )
        self.balance_url = urllib.parse.urljoin(
            self.base_url,
            'call/plaincall/balanceRemoteService.getBalances.dwr'
        )
        self.services_url = urllib.parse.urljoin(
            self.base_url,
            'call/plaincall/servicesRemoteService.getComponentsList.dwr'
        )

    def create_init_payload(self) -> str:
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
    def parse_init_response(response_body: str) -> str:
        regexp = r'dwr\.engine\.remote\.handleCallback\("[0-9]+","[0-9]+","([^"]+)"\);'
        return re.search(regexp, response_body).group(1)

    def create_balance_payload(self, dwr_id: str) -> str:
        balance_params = {
            'callCount': '1',
            'nextReverseAjaxIndex': '0',
            'c0-scriptName': 'balanceRemoteService',
            'c0-methodName': 'getBalances',
            'c0-id': '0',
            'batchId': '0',
            'instanceId': '0',
            'page': urllib.parse.quote_plus(self.page),
            'scriptSessionId': self.session_id(dwr_id),
        }
        return self.params_to_payload(balance_params)

    @staticmethod
    def parse_balance_response(response_body: str) -> str:
        begin_marker = re.escape(
            'dwr.engine.remote.handleCallback("0","0",'
            'dwr.engine.remote.newObject("BaseDwrTransferData",'
            '{responseStatus:dwr.engine.remote.newObject("ServiceDwrResponse",'
            '{messages:{},nextStep:null,status:"1"}),tableData:null,view:'
        )
        end_marker = re.escape('}));')
        regexp = r'^%s(.+)%s\s*$' % (begin_marker, end_marker)
        match = re.search(regexp, response_body, re.MULTILINE)
        return json.loads(match.group(1))

    def create_services_payload(self, dwr_id: str) -> str:
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
            'scriptSessionId': self.session_id(dwr_id),
        }
        return self.params_to_payload(service_params)

    def parse_services_response(self, response_body: str) -> str:
        return self.parse_balance_response(response_body)

    @staticmethod
    def params_to_payload(params: Dict[str, str]) -> str:
        return ''.join(["%s=%s\n" % (p_name, p_value) for p_name, p_value in params.items()])

    def session_id(self, dwr_id: str) -> str:
        return '%s/%s-%s' % (
            dwr_id,
            self.tokenify(int(time.time() * 1000)),
            self.tokenify(int(random.random() * 1e+16))
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

def xpath_text(parent_node: html.HtmlElement, xpath: str, allow_empty: bool) -> str:
    nodes = parent_node.xpath(xpath)
    if not nodes and allow_empty:
        return ""
    return nodes[0].text_content().strip()

def first_line(string: str) -> str:
    return "" if string == "" else string.splitlines()[0]

def main() -> None:
    import configparser
    config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    config = configparser.SafeConfigParser()
    config.read(os.path.join(config_dir, '24.play.pl.ini'))
    scraper = Scraper(config.get('auth', 'login'), config.get('auth', 'password'))
    scraper.log_in()
    balance_data = scraper.get_balance()
    services_data = scraper.list_services()
    scraper.log_out()
    for key, value in balance_data.items():
        print("%s: %s" % (key, value))
    for key, value in services_data.items():
        print("%s: %s" % (key, value))

if __name__ == '__main__':
    main()
