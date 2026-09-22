"""The GET endpoints of UBI's REST API that the live view is allowed to call.

The list is written out here rather than discovered from the running API, and that is the point of the module. The browser sends the name of an endpoint, never a path, so nothing the browser can say turns into a request the API was not meant to receive. Only GET endpoints appear, so the routes that place, modify and cancel orders cannot be reached from the monitor at all, and `POST /api/session/connect` is absent because calling it would mint a second application token and invalidate the one every other process is using.

Several endpoints name an instrument. UBI accepts either an `instrument_id` on its own, or an exchange and a segment together with the identity fields that segment's shape needs: a symbol for a security, an underlying and an expiry for a future, and those plus a strike and an option type for an option. All of those parameters are declared, and the caller fills in whichever pair it means.

Typical usage example:

  catalogue = ApiCatalogue()
  endpoint = catalogue.find('instruments_quote')
"""

from typing import Any

_INSTRUMENT_PARAMETERS = [
    {
        'name': 'instrument_id',
        'required': False,
        'example': '219dc728-34f8-5e37-8aff-5c0d48aa5778',
        'note': 'The unified instrument id. Give this on its own, or leave it empty and give the fields below.',
    },
    {
        'name': 'exchange',
        'required': False,
        'example': 'nse',
        'note': 'One of nse, bse, mcx or ncdex.',
    },
    {
        'name': 'segment',
        'required': False,
        'example': 'equities',
        'note': 'The segment without its exchange prefix, such as equities or equity_options.',
    },
    {
        'name': 'symbol',
        'required': False,
        'example': 'RELIANCE',
        'note': 'The symbol, for a security segment.',
    },
    {
        'name': 'underlying_symbol',
        'required': False,
        'example': 'NIFTY',
        'note': 'The underlying, for a future or an option.',
    },
    {
        'name': 'expiry_date',
        'required': False,
        'example': '2026-09-29',
        'note': 'The expiry, for a future or an option.',
    },
    {
        'name': 'strike_price',
        'required': False,
        'example': '25000',
        'note': 'The strike, for an option.',
    },
    {
        'name': 'option_type',
        'required': False,
        'example': 'CE',
        'note': 'CE or PE, for an option.',
    },
]

_DATE_PARAMETER = {
    'name': 'date',
    'required': False,
    'example': '2026-09-22',
    'note': 'The mapping date to read. Empty means the latest mapping.',
}

_ADJUSTED_PARAMETER = {
    'name': 'adjusted',
    'required': False,
    'example': 'true',
    'note': 'Whether splits and bonuses are applied. Defaults to true.',
}


class ApiCatalogue:
    """The fixed list of UBI GET endpoints, each with the parameters it takes."""

    def __init__(self):
        """Builds the catalogue."""
        self._endpoints = self._build()

    def endpoints(self) -> list[dict[str, Any]]:
        """Lists every endpoint the live view may call.

        Returns:
            list[dict[str, Any]]: One entry per endpoint, each with "name", "group", "label", "path", "authenticated", "note" and "parameters".
        """
        return [dict(endpoint) for endpoint in self._endpoints]

    def find(self, name: str) -> dict[str, Any] | None:
        """Looks one endpoint up by its name.

        Args:
            name (str): The endpoint's name, such as "instruments_quote".

        Returns:
            dict[str, Any] | None: The endpoint, or None when no endpoint has that name.
        """
        for endpoint in self._endpoints:
            if endpoint['name'] == name:
                return dict(endpoint)
        return None

    def parameter_names(self, name: str) -> list[str]:
        """Names the query parameters one endpoint accepts.

        Args:
            name (str): The endpoint's name.

        Returns:
            list[str]: The parameter names, which is empty when the endpoint is unknown or takes none.
        """
        endpoint = self.find(name)
        if endpoint is None:
            return []
        return [parameter['name'] for parameter in endpoint['parameters']]

    def _build(self) -> list[dict[str, Any]]:
        """Writes out every endpoint.

        Returns:
            list[dict[str, Any]]: The endpoints, grouped in the order the page shows them.
        """
        return [
            self._endpoint(
                'greeting',
                'Session',
                'Greeting',
                '/',
                'The unauthenticated greeting, which says the API is up.',
                [],
                authenticated=False,
            ),
            self._endpoint(
                'session_status',
                'Session',
                'Session status',
                '/session/status',
                'Whether the application token in force is still valid.',
                [],
            ),
            self._endpoint(
                'users_details',
                'Account',
                'User details',
                '/users/details',
                'Every user profile document, and each broker\'s profile of the account.',
                [],
            ),
            self._endpoint(
                'brokers_details',
                'Account',
                'Broker details',
                '/brokers/details',
                'Details for every broker.',
                [],
            ),
            self._endpoint(
                'exchanges_details',
                'Account',
                'Exchange details',
                '/exchanges/details',
                'Details for every exchange, including trading hours and holidays.',
                [],
            ),
            self._endpoint(
                'instruments_segments',
                'Instruments',
                'Segments',
                '/instruments/segments',
                'Every segment mapped today, with how many instruments each holds.',
                [],
            ),
            self._endpoint(
                'instruments_master',
                'Instruments',
                'Master',
                '/instruments/master',
                'Every instrument in an exchange and segment. Either may be "all", which returns the whole half-million and will be truncated.',
                [
                    {
                        'name': 'exchange',
                        'required': False,
                        'example': 'nse',
                        'note': 'An exchange, or "all".',
                    },
                    {
                        'name': 'segment',
                        'required': False,
                        'example': 'equities',
                        'note': 'A segment, or "all".',
                    },
                    _DATE_PARAMETER,
                ],
            ),
            self._endpoint(
                'instruments_search',
                'Instruments',
                'Search',
                '/instruments/search',
                'Instruments in one segment whose symbol or underlying contains the text.',
                [
                    {
                        'name': 'exchange',
                        'required': True,
                        'example': 'nse',
                        'note': 'One of nse, bse, mcx or ncdex.',
                    },
                    {
                        'name': 'segment',
                        'required': True,
                        'example': 'equities',
                        'note': 'The segment without its exchange prefix.',
                    },
                    {
                        'name': 'q',
                        'required': False,
                        'example': 'RELIANCE',
                        'note': 'The text to look for.',
                    },
                    {
                        'name': 'limit',
                        'required': False,
                        'example': '50',
                        'note': 'How many matches to return.',
                    },
                    _DATE_PARAMETER,
                ],
            ),
            self._endpoint(
                'instruments_details',
                'Instruments',
                'Details',
                '/instruments/details',
                'One instrument\'s identity, seen dates and every broker\'s handle for it.',
                _INSTRUMENT_PARAMETERS + [
                    _DATE_PARAMETER,
                ],
            ),
            self._endpoint(
                'instruments_additional_details',
                'Instruments',
                'Additional details',
                '/instruments/additional_details',
                'The extra attributes each broker\'s own instrument file carries for one instrument.',
                _INSTRUMENT_PARAMETERS + [
                    _DATE_PARAMETER,
                ],
            ),
            self._endpoint(
                'instruments_ltp',
                'Prices',
                'Last traded price',
                '/instruments/ltp',
                'The last traded price of one instrument.',
                _INSTRUMENT_PARAMETERS,
            ),
            self._endpoint(
                'instruments_ohlc',
                'Prices',
                'Open, high, low and close',
                '/instruments/ohlc',
                'The last price with the day\'s open, high and low, and the previous close.',
                _INSTRUMENT_PARAMETERS,
            ),
            self._endpoint(
                'instruments_quote',
                'Prices',
                'Quote',
                '/instruments/quote',
                'The full unified quote document for one instrument, market depth included.',
                _INSTRUMENT_PARAMETERS,
            ),
            self._endpoint(
                'instruments_prices',
                'Prices',
                'Historical prices',
                '/instruments/prices',
                'Candles for one instrument, either between two dates or for the last so many days.',
                _INSTRUMENT_PARAMETERS + [
                    {
                        'name': 'interval',
                        'required': True,
                        'example': 'day',
                        'note': 'The candle interval.',
                    },
                    {
                        'name': 'days',
                        'required': False,
                        'example': '30',
                        'note': 'The last so many days. Give this, or "from" and "to", but not both.',
                    },
                    {
                        'name': 'from',
                        'required': False,
                        'example': '2026-08-01',
                        'note': 'The first date.',
                    },
                    {
                        'name': 'to',
                        'required': False,
                        'example': '2026-09-22',
                        'note': 'The last date.',
                    },
                    _ADJUSTED_PARAMETER,
                    {
                        'name': 'known_as_of',
                        'required': False,
                        'example': '2026-09-01',
                        'note': 'Apply only the adjustments known by this date.',
                    },
                ],
            ),
            self._endpoint(
                'instruments_ticks',
                'Prices',
                'Ticks',
                '/instruments/ticks',
                'Every stored tick for one instrument between two instants. A wide range returns a great many rows and will be truncated.',
                _INSTRUMENT_PARAMETERS + [
                    {
                        'name': 'start',
                        'required': True,
                        'example': '2026-09-22T09:15:00',
                        'note': 'The first instant.',
                    },
                    {
                        'name': 'end',
                        'required': True,
                        'example': '2026-09-22T09:30:00',
                        'note': 'The last instant.',
                    },
                    _ADJUSTED_PARAMETER,
                ],
            ),
            self._endpoint(
                'orders_details',
                'Orders',
                'Orders',
                '/orders/details',
                'Today\'s orders at every broker, with how each broker\'s data was read.',
                [],
            ),
            self._endpoint(
                'orders_trades',
                'Orders',
                'Trades',
                '/orders/trades',
                'Today\'s trades at every broker.',
                [],
            ),
            self._endpoint(
                'portfolio_funds',
                'Portfolio',
                'Funds',
                '/portfolio/funds',
                'The account\'s funds summed across every broker.',
                [],
            ),
            self._endpoint(
                'portfolio_holdings',
                'Portfolio',
                'Holdings',
                '/portfolio/holdings',
                'The account\'s holdings merged across every broker and priced.',
                [],
            ),
            self._endpoint(
                'portfolio_positions',
                'Portfolio',
                'Positions',
                '/portfolio/positions',
                'The account\'s open positions, net and day, merged across every broker.',
                [],
            ),
        ]

    def _endpoint(
        self,
        name: str,
        group: str,
        label: str,
        path: str,
        note: str,
        parameters: list[dict[str, Any]],
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Describes one endpoint.

        Args:
            name (str): The name the browser asks for the endpoint by.
            group (str): The heading the page files it under.
            label (str): The human label.
            path (str): The path after the API's own `/api` prefix.
            note (str): One sentence saying what the endpoint answers.
            parameters (list[dict[str, Any]]): The query parameters it accepts.
            authenticated (bool): Whether the request needs the application token.

        Returns:
            dict[str, Any]: The endpoint.
        """
        return {
            'name': name,
            'group': group,
            'label': label,
            'path': path,
            'note': note,
            'authenticated': authenticated,
            'parameters': parameters,
        }
