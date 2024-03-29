**Note: the script does not work anymore due to SMS token authentication
introduced by the mobile carrier.**

This is a [web scraper](https://en.wikipedia.org/wiki/Web_scraping) for your
profile at the [Play](https://en.wikipedia.org/wiki/Play_%28telecommunications%29)
mobile network operator site: [https://24.play.pl/](https://24.play.pl/).

It can be useful if you want to automatically monitor your prepaid account
balance.

## Setup

Copy the example configuration file `24.play.pl-example.ini` into
`~/.config/24.play.pl.ini`. Make sure it is not world readable.

	cp 24.play.pl-example.ini ~/.config/24.play.pl.ini
	chmod 600 ~/.config/24.play.pl.ini

Enter your login and password in the `~/.config/24.play.pl.ini` file.

You'll also need a Firefox driver for [Selenium](https://www.selenium.dev/):

	latest_release_url='https://github.com/mozilla/geckodriver/releases/latest'

	download_xpath='string(//a[contains(@href, "linux64.tar.gz") and not(contains(@href, ".tar.gz.asc"))]/@href)'

	download_url='https://github.com'$(curl -s -S -L "$latest_release_url" | xmllint --html --xpath "$download_xpath" - 2>/dev/null)

	mkdir selenium-drivers
	curl -s -S -L "$download_url" | tar zxp -C selenium-drivers

## Usage

Run:

	./scrape.py

Output will be similar to:

	balance_PLN: 11.22
	outgoing_expiration_date: YYYY-MM-DD
	incoming_expiration_date: YYYY-MM-DD
	SMS_all_count: 0
	free_data_GB: 33.4
	extend_7days: False
	extend_31days: False
	extend_365days: False
	cheaper_roaming_EU_data_GB: 5.0
	voice_bundle_1000min_UA: False
	voice_bundle_1000min_UA_Viber_10GB: False
	voice_29_BD: False
	voice_29_IN: False
	voice_29_NP: False
	cheaper_BD: False
	cheaper_IN: False
	cheaper_NP: False
	voice_bundle_1000min_UA_unlimited_PL_recurring: False
	voice_bundle_1000min_UA_unlimited_PL: False
	no_data_limit_day: False
	no_data_limit_month_recurring: False
	no_data_limit_month: True
	no_data_limit_nights_recurring: False
	no_data_limit_nights: False
	no_data_limit_week: False
	roaming_EU_data_bundle_1GB: False
	roaming_EU_data_bundle_3GB: False
	roaming_AE_data_bundle_150MB: False
	roaming_data_bundle_1GB: False
	roaming_data_bundle_300MB: False
	cheaper_UA: False
	roaming: False
	roaming_EU_data_bundle_500MB: False

The script is also importable.
