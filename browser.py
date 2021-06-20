from time import sleep

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver import Firefox, FirefoxProfile
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support.ui import WebDriverWait


def create_driver(debug: bool) -> WebDriver:
    firefox_options = Options()
    if not debug:
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

    def find_username_input(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("input[name='msisdn']")

    def find_username_submit_button(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("button[name='begin']")

    def find_password_input(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("input[name='password']")

    def find_password_submit_button(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("button[name='openam-pass-submit']")

    def username_form_is_loaded(driver: WebDriver) -> bool:
        return bool(
            find_username_input(driver)
            and find_username_submit_button(driver)
        )

    def password_form_is_loaded(driver: WebDriver) -> bool:
        return bool(
            find_password_input(driver)
            and find_password_submit_button(driver)
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

    wait.until(username_form_is_loaded)
    find_username_input(driver).send_keys(username)
    sleep(2)
    find_username_submit_button(driver).click()

    wait.until(password_form_is_loaded)
    find_password_input(driver).send_keys(password)
    sleep(2)
    find_password_submit_button(driver).click()

    wait.until(user_profile_is_loaded)
    try:
        dismiss_news_modal(driver, timeout)
    except TimeoutException:
        pass


def dismiss_news_modal(driver: WebDriver, timeout: int) -> None:

    def find_dismiss_news_button(driver: WebDriver) -> WebElement:
        return driver.find_element_by_css_selector("div#newSsoInfoModal button.fancybox-close")

    wait = WebDriverWait(driver, timeout)
    wait.until(find_dismiss_news_button)
    find_dismiss_news_button(driver).click()


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
    logout_button = driver.find_element_by_xpath("//a[.='Wyloguj']")
    logout_button.click()
    wait.until(lambda driver: "Logowanie" in driver.title)
