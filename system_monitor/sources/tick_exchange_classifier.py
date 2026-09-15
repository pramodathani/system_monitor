"""Maps each broker's spelling of an exchange to a trading calendar.

Every broker's live tick carries an `exchange` field, but each broker spells it its own way. On 2026-09-15 the values seen were "MCX_COMM" and "NSE_EQ" (Dhan), "nse_cm" and "mcx_fo" (Kotak), "NSECM" (Wisdom Capital), "NSE" and "MCX" (Flattrade, Fyers, Shoonya, Stoxkart), and "mcx" and "nse" (Zerodha and unified).

Typical usage example:

  classifier = TickExchangeClassifier()
  classifier.calendar_key('MCX_COMM')   # ('mcx', 'commodity')
"""


class TickExchangeClassifier:
    """Turns a tick's exchange text into an (exchange, calendar) pair."""

    def calendar_key(self, exchange_text: object) -> tuple[str, str] | None:
        """Finds the calendar an exchange value trades on.

        Args:
            exchange_text (object): The tick's exchange field, usually a string.

        Returns:
            tuple[str, str] | None: The (exchange, calendar) pair, or None when the value is not recognised.
        """
        if not isinstance(exchange_text, str):
            return None
        text = exchange_text.strip().lower()
        if text.startswith('mcx'):
            return ('mcx', 'commodity')
        if text.startswith('ncdex'):
            return ('ncdex', 'commodity')
        if text == 'cds' or text.startswith('nse_cd') or 'currency' in text:
            return ('nse', 'currency')
        if text.startswith(('bse', 'bfo')):
            return ('bse', 'equity')
        if text.startswith(('nse', 'nfo')):
            return ('nse', 'equity')
        return None
