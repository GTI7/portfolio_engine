from importers.ibkr_flex_query_importer import IbkrFlexQueryImporter


def wrap(inner: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryName="Test" type="AF">
  <FlexStatements count="1">
    <FlexStatement accountId="U1234567" fromDate="20260101" toDate="20260131">
      {inner}
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>"""


def test_parses_a_buy_trade():
    xml = wrap(
        '<Trades>'
        '<Trade symbol="AAPL" tradeDate="20260115" quantity="10" tradePrice="150.25" '
        'buySell="BUY" currency="USD" transactionID="9988776655" tradeMoney="1502.50" '
        'ibCommission="-1.00" />'
        '</Trades>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert result.rejected == []
    assert len(result.transactions) == 1
    txn = result.transactions[0]
    assert txn.type.value == "buy"
    assert txn.symbol == "AAPL"
    assert txn.shares == 10.0
    assert txn.price == 150.25
    assert txn.amount == 1502.50
    assert txn.id == "ibkr-9988776655"
    assert txn.currency == "USD"


def test_parses_a_sell_trade_with_negative_quantity():
    """IBKR reports SELL quantities as negative - shares must still end up
    positive (Transaction's own validation requires shares > 0 for SELL).
    """
    xml = wrap(
        '<Trades>'
        '<Trade symbol="MSFT" tradeDate="20260120" quantity="-5" tradePrice="300.00" '
        'buySell="SELL" currency="USD" transactionID="1122334455" />'
        '</Trades>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert len(result.transactions) == 1
    txn = result.transactions[0]
    assert txn.type.value == "sell"
    assert txn.shares == 5.0  # positive, despite quantity="-5"
    assert txn.amount == 1500.0  # computed from price*shares since no tradeMoney given


def test_parses_a_dividend_cash_transaction():
    xml = wrap(
        '<CashTransactions>'
        '<CashTransaction type="Dividends" symbol="AAPL" amount="12.50" '
        'dateTime="20260201" currency="USD" transactionID="5566778899" />'
        '</CashTransactions>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert len(result.transactions) == 1
    txn = result.transactions[0]
    assert txn.type.value == "dividend"
    assert txn.symbol == "AAPL"
    assert txn.amount == 12.50


def test_deposits_withdrawals_split_by_amount_sign():
    xml = wrap(
        '<CashTransactions>'
        '<CashTransaction type="Deposits/Withdrawals" amount="5000.00" '
        'dateTime="20260101" currency="USD" transactionID="1" />'
        '<CashTransaction type="Deposits/Withdrawals" amount="-500.00" '
        'dateTime="20260105" currency="USD" transactionID="2" />'
        '</CashTransactions>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert len(result.transactions) == 2
    types = {t.type.value for t in result.transactions}
    assert types == {"deposit", "withdrawal"}
    deposit = next(t for t in result.transactions if t.type.value == "deposit")
    withdrawal = next(t for t in result.transactions if t.type.value == "withdrawal")
    assert deposit.amount == 5000.0
    assert withdrawal.amount == 500.0  # unsigned, per Transaction's own convention


def test_fees_are_recognized():
    xml = wrap(
        '<CashTransactions>'
        '<CashTransaction type="Other Fees" amount="-10.00" '
        'dateTime="20260110" currency="USD" transactionID="3" />'
        '</CashTransactions>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert len(result.transactions) == 1
    assert result.transactions[0].type.value == "fee"
    assert result.transactions[0].amount == 10.0


def test_unsupported_cash_transaction_type_is_skipped_with_warning():
    xml = wrap(
        '<CashTransactions>'
        '<CashTransaction type="Broker Interest Received" amount="1.23" '
        'dateTime="20260110" currency="USD" transactionID="4" />'
        '</CashTransactions>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert result.transactions == []
    assert result.rejected == []  # not a rejection - it's a legitimately unsupported category
    assert len(result.warnings) == 1
    assert "Broker Interest Received" in result.warnings[0]


def test_trade_missing_transaction_id_is_rejected():
    xml = wrap(
        '<Trades>'
        '<Trade symbol="AAPL" tradeDate="20260115" quantity="10" tradePrice="150.0" '
        'buySell="BUY" currency="USD" />'
        '</Trades>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert result.transactions == []
    assert len(result.rejected) == 1
    assert "transactionID" in result.rejected[0].error


def test_malformed_xml_produces_a_warning_not_a_crash():
    result = IbkrFlexQueryImporter().parse("<not><valid</xml>", portfolio_id="demo")
    assert result.transactions == []
    assert len(result.warnings) == 1
    assert "parse XML" in result.warnings[0]


def test_date_formats_yyyymmdd_and_yyyymmdd_semicolon_time():
    xml = wrap(
        '<Trades>'
        '<Trade symbol="AAPL" tradeDate="20260115;093000" quantity="1" tradePrice="150.0" '
        'buySell="BUY" currency="USD" transactionID="1" />'
        '</Trades>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert len(result.transactions) == 1
    assert result.transactions[0].date.year == 2026
    assert result.transactions[0].date.month == 1
    assert result.transactions[0].date.day == 15


def test_portfolio_id_stamped_on_all_transactions():
    xml = wrap(
        '<Trades>'
        '<Trade symbol="AAPL" tradeDate="20260115" quantity="1" tradePrice="150.0" '
        'buySell="BUY" currency="USD" transactionID="1" />'
        '</Trades>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="my_retirement_fund")
    assert result.transactions[0].portfolio_id == "my_retirement_fund"


def test_mixed_trades_and_cash_transactions_in_one_file():
    xml = wrap(
        '<Trades>'
        '<Trade symbol="AAPL" tradeDate="20260115" quantity="10" tradePrice="150.0" '
        'buySell="BUY" currency="USD" transactionID="1" />'
        '</Trades>'
        '<CashTransactions>'
        '<CashTransaction type="Dividends" symbol="AAPL" amount="5.00" '
        'dateTime="20260201" currency="USD" transactionID="2" />'
        '<CashTransaction type="Deposits/Withdrawals" amount="1000.00" '
        'dateTime="20260101" currency="USD" transactionID="3" />'
        '</CashTransactions>'
    )
    result = IbkrFlexQueryImporter().parse(xml, portfolio_id="demo")

    assert len(result.transactions) == 3
    types = sorted(t.type.value for t in result.transactions)
    assert types == ["buy", "deposit", "dividend"]
