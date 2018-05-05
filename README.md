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

	{'Konto': '11,22 zł', 'Data ważności połączeń wychodzących': 'DD.MM.YYYY', 'Data ważności połączeń przychodzących': 'DD.MM.YYYY', 'Liczba promocyjnych GB': '33,4 GB', 'Limit GB w roamingu UE': '5 GB'}

The script is also importable. The `get_balance` method returns a dict with parsed data.
