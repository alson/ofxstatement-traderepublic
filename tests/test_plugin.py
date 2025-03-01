from decimal import Decimal
import os

from ofxstatement.ui import UI

from ofxstatement_traderepublic.plugin import TradeRepublicPlugin


def test_plugin_csv():
    plugin = TradeRepublicPlugin(UI(), {})
    here = os.path.dirname(__file__)
    filename = os.path.join(here, "traderepublic-statement.csv")

    parser = plugin.get_parser(filename)
    statement = parser.parse()
    statement.assert_valid()
    assert statement is not None
    assert statement.end_balance == Decimal(86)
    assert len(statement.lines) == 6
    assert statement.lines[0].amount == Decimal("-7.01")
    assert statement.lines[0].date.year == 2025
    assert statement.lines[0].date.month == 1
    assert statement.lines[0].date.day == 20
    assert statement.lines[0].memo == "Some Shop"
    assert statement.lines[0].trntype == "POS"
    assert statement.lines[1].trntype == "XFER"
    assert statement.lines[1].memo == "Jane Doe"
    assert statement.lines[2].trntype == "DIV"
    assert statement.lines[2].memo == "MSCI USA USD (Dist)"
    assert statement.lines[3].trntype == "INT"
    assert statement.lines[5].trntype == "DEBIT"
    assert statement.lines[5].memo == "MSCI USA USD (Dist) - IE0000000000 - 0.512345"


def test_plugin_json():
    plugin = TradeRepublicPlugin(UI(), {})
    here = os.path.dirname(__file__)
    filename = os.path.join(here, "traderepublic-events.json")

    parser = plugin.get_parser(filename)
    statement = parser.parse()
    statement.assert_valid()
    assert statement is not None
    delta = Decimal("0.01")
    assert statement.end_balance.quantize(delta) == Decimal("98.77006500000002").quantize(delta)
    assert len(statement.lines) == 9
