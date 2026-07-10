from importers.generic_csv_importer import GenericCsvImporter

HEADER = "id,type,date,symbol,shares,price,amount,currency,notes\n"


def test_parses_a_simple_buy_row():
    csv_content = (
        HEADER + "t1,buy,2026-01-15T00:00:00Z,AAPL,10,150.0,1500.0,USD,\n"
    )
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert len(result.transactions) == 1
    assert result.rejected == []
    txn = result.transactions[0]
    assert txn.id == "t1"
    assert txn.type.value == "buy"
    assert txn.symbol == "AAPL"
    assert txn.shares == 10.0
    assert txn.amount == 1500.0


def test_parses_a_deposit_with_no_symbol_columns():
    csv_content = HEADER + "d1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,initial funding\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert len(result.transactions) == 1
    txn = result.transactions[0]
    assert txn.type.value == "deposit"
    assert txn.symbol is None
    assert txn.notes == "initial funding"


def test_missing_id_generates_deterministic_id():
    csv_content = HEADER + ",deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert len(result.transactions) == 1
    assert result.transactions[0].id.startswith("gen-")


def test_missing_id_is_stable_across_two_parses_of_the_same_file():
    csv_content = HEADER + ",deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    result1 = GenericCsvImporter().parse(csv_content, portfolio_id="demo")
    result2 = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert result1.transactions[0].id == result2.transactions[0].id


def test_unrecognized_type_is_rejected_not_raised():
    csv_content = HEADER + "t1,teleport,2026-01-01T00:00:00Z,,,,100.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert result.transactions == []
    assert len(result.rejected) == 1
    assert result.rejected[0].source_line == 2
    assert "teleport" in result.rejected[0].error


def test_unparseable_date_is_rejected():
    csv_content = HEADER + "t1,deposit,not-a-date,,,,100.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert result.transactions == []
    assert len(result.rejected) == 1
    assert "date" in result.rejected[0].error


def test_unparseable_amount_is_rejected():
    csv_content = HEADER + "t1,deposit,2026-01-01T00:00:00Z,,,,not-a-number,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert result.transactions == []
    assert len(result.rejected) == 1
    assert "amount" in result.rejected[0].error


def test_transaction_validation_failure_is_rejected_not_raised():
    """A buy row missing shares/price fails Transaction's own validation -
    the importer must catch this, not propagate it, and must reuse the
    exact same error message Transaction itself produces.
    """
    csv_content = HEADER + "t1,buy,2026-01-01T00:00:00Z,AAPL,,,1000.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert result.transactions == []
    assert len(result.rejected) == 1
    assert "requires shares" in result.rejected[0].error


def test_mix_of_valid_and_invalid_rows_partitions_correctly():
    csv_content = (
        HEADER
        + "t1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
        + "t2,teleport,2026-01-02T00:00:00Z,,,,100.0,USD,\n"
        + "t3,withdrawal,2026-01-03T00:00:00Z,,,,50.0,USD,\n"
    )
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert len(result.transactions) == 2
    assert len(result.rejected) == 1
    assert result.rejected[0].source_line == 3  # the teleport row, 1-indexed with header


def test_missing_required_column_produces_a_warning_not_a_crash():
    csv_content = "type,date,amount\nbuy,2026-01-01T00:00:00Z,100.0\n"  # no currency column
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert result.transactions == []
    assert len(result.warnings) == 1
    assert "currency" in result.warnings[0]


def test_empty_file_produces_a_warning_not_a_crash():
    result = GenericCsvImporter().parse("", portfolio_id="demo")
    assert result.transactions == []
    assert len(result.warnings) == 1


def test_portfolio_id_is_stamped_on_every_transaction():
    csv_content = HEADER + "t1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="my_portfolio")
    assert result.transactions[0].portfolio_id == "my_portfolio"


def test_case_insensitive_headers_and_type_values():
    csv_content = "ID,TYPE,DATE,SYMBOL,SHARES,PRICE,AMOUNT,CURRENCY,NOTES\n"
    csv_content += "t1,DEPOSIT,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert len(result.transactions) == 1
    assert result.transactions[0].type.value == "deposit"


def test_leading_bom_is_stripped_not_left_to_break_the_header():
    """Excel writes a UTF-8 BOM by default - a very common source of
    broker CSV exports. Without stripping it, the header's first column
    parses as '\\ufeffid' instead of 'id'.
    """
    csv_content = "\ufeff" + HEADER + "t1,deposit,2026-01-01T00:00:00Z,,,,1000.0,USD,\n"
    result = GenericCsvImporter().parse(csv_content, portfolio_id="demo")

    assert len(result.transactions) == 1
    assert result.warnings == []
    assert result.transactions[0].id == "t1"
