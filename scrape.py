#!/usr/bin/env python3

import os
import urllib.parse
import random
import time
import re
import math
import json

import requests
from lxml import html

class Scraper(object):

    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.start_url = 'https://24.play.pl/'
        self.logout_url = 'https://konto.play.pl/opensso/UI/Logout'
        self.session = requests.Session()
        self.dwr = None
        self.dwr_id = None

    def log_in(self):
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

    def get_balance(self):
        self.init_dwr()
        response = self.session.post(
            self.dwr.balance_url,
            self.dwr.create_balance_payload(self.dwr_id)
        )
        response.raise_for_status()
        balance_html = self.dwr.parse_balance_response(response.text)
        return self.parse_balance_data(balance_html)

    def list_services(self):
        self.init_dwr()
        response = self.session.post(
            self.dwr.services_url,
            self.dwr.create_services_payload(self.dwr_id)
        )
        response.raise_for_status()
        services_html = self.dwr.parse_services_response(response.text)
        return self.parse_services_data(services_html)

    def log_out(self):
        response = self.session.get(self.logout_url)
        response.raise_for_status()

    def init_dwr(self):
        if self.dwr is not None:
            return
        # emulate the AJAX end of a Java DWR bridge
        self.dwr = DWR('https://24.play.pl/Play24/dwr/', '/Play24/Welcome')
        response = self.session.post(self.dwr.init_url, self.dwr.create_init_payload())
        response.raise_for_status()
        self.dwr_id = self.dwr.parse_init_response(response.text)
        self.session.cookies.set('DWRSESSIONID', self.dwr_id, domain='24.play.pl')

    @staticmethod
    def parse_balance_data(html_code):

        def xpath_text(parent_node, xpath):
            return parent_node.xpath(xpath)[0].text_content().strip()

        row_xpath = (
            "//div[contains(@class, 'row-fluid')]"
            "/div[contains(@class, 'row-fluid') and not(contains(@class, 'collapse'))]"
        )
        label_xpath = "./span[contains(@class, 'span4')]"
        value_xpath = "./span[contains(@class, 'span5')]"
        return {
            xpath_text(row_node, label_xpath):
            xpath_text(row_node, value_xpath).splitlines()[0].strip()
            for row_node in html.fromstring(html_code).xpath(row_xpath)
        }

    @staticmethod
    def parse_services_data(html_code):

        def xpath_text(parent_node, xpath):
            return parent_node.xpath(xpath)[0].text_content().strip()

        row_xpath = "//table[contains(@class, 'services')]/tbody/tr"
        label_xpath = "./td/span/span/span[contains(@class, 'header')]"
        value_xpath = "./td[contains(@class, 'status')]/span"
        return {
            xpath_text(row_node, label_xpath):
            xpath_text(row_node, value_xpath).splitlines()[0].strip()
            for row_node in html.fromstring(html_code).xpath(row_xpath)
        }

    def follow_js_form_redirection(self, response):
        form = html.fromstring(response.content).xpath("//form[1]")[0]
        post_data = self.form_inputs_to_post_data(form)
        response = self.session.post(form.action, data=post_data)
        response.raise_for_status()
        return response

    @staticmethod
    def form_inputs_to_post_data(form):
        return {i.name: i.value for i in form.xpath(".//input")}

    @staticmethod
    def find_login_form(page_html):

        def form_has_input(form, input_name):
            return bool(form.xpath(".//input[@name='%s']" % (input_name,)))

        for form in html.fromstring(page_html).xpath("//form"):
            if form_has_input(form, 'IDToken1') and form_has_input(form, 'IDToken2'):
                return form

class DWR(object):

    def __init__(self, base_url, page):
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
            'call/plaincall/templateRemoteService.view.dwr'
        )

    def create_init_payload(self):
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
    def parse_init_response(response_body):
        regexp = r'dwr\.engine\.remote\.handleCallback\("[0-9]+","[0-9]+","([^"]+)"\);'
        return re.search(regexp, response_body).group(1)

    def create_balance_payload(self, dwr_id):
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
    def parse_balance_response(response_body):
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

    def create_services_payload(self, dwr_id):
        service_params = {
            'callCount': '1',
            'nextReverseAjaxIndex': '0',
            'c0-scriptName': 'templateRemoteService',
            'c0-methodName': 'view',
            'c0-id': '0',
            'c0-param0': 'string:PACKAGES',
            'batchId': '0',
            'instanceId': '0',
            'page': urllib.parse.quote_plus(self.page),
            'scriptSessionId': self.session_id(dwr_id),
        }
        return self.params_to_payload(service_params)

    def parse_services_response(self, response_body):
        return self.parse_balance_response(response_body)

    @staticmethod
    def params_to_payload(params):
        return ''.join(["%s=%s\n" % (p_name, p_value) for p_name, p_value in params.items()])

    def session_id(self, dwr_id):
        return '%s/%s-%s' % (
            dwr_id,
            self.tokenify(int(time.time() * 1000)),
            self.tokenify(int(random.random() * 1e+16))
        )

    @staticmethod
    def tokenify(number):
        # emulate the JavaScript `dwr.engine.util.tokenify` function
        tokenbuf = []
        charmap = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ*$"
        remainder = number
        while remainder > 0:
            tokenbuf.append(charmap[remainder & 0x3F])
            remainder = math.floor(remainder / 64)
        return ''.join(tokenbuf)

def main():
    import configparser
    config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    config = configparser.SafeConfigParser()
    config.read(os.path.join(config_dir, '24.play.pl.ini'))
    scraper = Scraper(config.get('auth', 'login'), config.get('auth', 'password'))
    scraper.log_in()
    balance_data = scraper.get_balance()
    services_data = scraper.list_services()
    scraper.log_out()
    print(balance_data)
    print(services_data)

if __name__ == '__main__':
    main()
