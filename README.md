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

## Usage

Run:

	./scrape.py

Output will be similar to:

	balance_PLN: 11.22
	outgoing_expiration_date: YYYY-MM-DD
	incoming_expiration_date: YYYY-MM-DD
	data_sale:
	free_data_GB: 33.4
	free_youtube_summer_recurring: False
	cheaper_roaming_EU_data_GB: 5.0
	premium_services_limit_PLN: 35.0
	voice_bundle_1000min_UA: False
	no_data_limit_day: False
	no_data_limit_month_recurring: False
	no_data_limit_month: True
	no_data_limit_nights_recurring: False
	no_data_limit_nights: False
	data_bundle_5GB: False
	no_data_limit_week: False
	roaming_EU_data_bundle_1GB: False
	roaming_EU_data_bundle_3GB: False
	roaming_AE_data_bundle_150MB: False
	roaming_data_bundle_1GB: False
	roaming_data_bundle_300MB: False
	cheaper_UA: False
	roaming: False
	roaming_EU_data_bundle_500MB: False

The script is also importable. The `get_balance` and `list_services` methods
return dicts with parsed data.
