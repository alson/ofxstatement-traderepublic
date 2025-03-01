import csv
from decimal import Decimal
import json
from operator import itemgetter
from typing import Dict, Iterable, Optional, TextIO, Union
from datetime import datetime

from ofxstatement.plugin import Plugin
from ofxstatement.parser import CsvStatementParser, StatementParser
from ofxstatement.statement import (Statement, StatementLine, recalculate_balance, Currency, InvestStatementLine, generate_transaction_id)

class TradeRepublicCsvParser(CsvStatementParser):
    def __init__(self, fin: TextIO) -> None:
        super().__init__(fin)

    def parse(self) -> Statement:
        statement = super().parse()
        recalculate_balance(statement)
        return statement

    def split_records(self) -> Iterable[Dict[str, str]]:
        return csv.DictReader(self.fin, delimiter=";")

    def parse_record(self, line: Dict[str, str]) -> StatementLine:
        stmt_line = StatementLine()
        stmt_line.date = datetime.fromisoformat(line["Date"])
        stmt_line.amount = Decimal(line["Value"])
        stmt_line.memo = line["Note"]
        if line["Type"] == "Deposit":
            if line["Note"].startswith("Card Refund"):
                stmt_line.trntype = "CREDIT"
                stmt_line.memo = line["Note"].split("Card Refund - ")[1]
            else:
                stmt_line.trntype = "XFER"
        elif line["Type"] == "Removal":
            if line["Note"].startswith("Card Payment"):
                stmt_line.trntype = "POS"
                stmt_line.memo = line["Note"].split("Card Payment - ")[1]
            else:
                stmt_line.trntype = "DEBIT"
        elif line["Type"] == "Dividend":
            stmt_line.trntype = "DIV"
        elif line["Type"] == "Interest":
            stmt_line.trntype = "INT"
        elif line["Type"] == "Buy":
            stmt_line.trntype = "DEBIT"
            stmt_line.memo = line["Note"] + " - " + line["ISIN"] + " - " + line["Shares"]
        stmt_line.id = generate_transaction_id(stmt_line)
        return stmt_line

class TradeRepublicJsonParser(StatementParser[Dict]):
    def __init__(self, fin: TextIO) -> None:
        super().__init__()
        self.fin = fin

    def parse(self) -> Statement:
        statement = Statement()
        events = json.load(self.fin)
        for event in sorted(events, key=itemgetter("timestamp")):
            stmt_line = self.parse_record(event)
            if stmt_line:
                stmt_line.assert_valid()
                statement.lines.append(stmt_line)
        recalculate_balance(statement)
        return statement

    def parse_record(self, event: Dict) -> Optional[StatementLine]:
        if event["eventType"] not in {"card_successful_transaction", "PAYMENT_INBOUND", "card_refund", "INTEREST_PAYOUT", "INTEREST_PAYOUT_CREATED","PAYMENT_INBOUND_CREDIT_CARD", "ssp_corporate_action_invoice_cash", "SAVINGS_PLAN_INVOICE_CREATED", "benefits_saveback_execution"}:
            return None
        if event["status"] != "EXECUTED":
            return None
        stmt_line = InvestStatementLine() if event["eventType"] in ("SAVINGS_PLAN_INVOICE_CREATED", "benefits_saveback_execution") else StatementLine()
        stmt_line.id = event["id"]
        stmt_line.date = datetime.strptime(event["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z")
        stmt_line.amount = Decimal(event["amount"]["value"])
        stmt_line.currency = Currency(event["amount"]["currency"])
        stmt_line.memo = event["title"]
        if event.get("subAmount"):
            stmt_line.orig_currency = Currency(event["amount"]["currency"], event["subAmount"]["value"]/event["amount"]["value"])
        if event["eventType"] == "card_successful_transaction":
            stmt_line.trntype = "POS"
        elif event["eventType"] == "card_refund":
            stmt_line.trntype = "CREDIT"
        elif event["eventType"] == "PAYMENT_INBOUND":
            stmt_line.trntype = "XFER"
            payee_name = ""
            payee_iban = ""
            for section in event["details"]["sections"]:
                if section["title"] == "Übersicht":
                    for datum in section["data"]:
                        if datum["title"] == "Von":
                            stmt_line.memo = datum["detail"]["text"]
                            payee_name = datum["detail"]["text"]
                        elif datum["title"] == "IBAN":
                            payee_iban = datum["detail"]["text"]
            if payee_name and payee_iban:
                stmt_line.payee = payee_iban + " - " + payee_name
            elif payee_name:
                stmt_line.payee = payee_name
            elif payee_iban:
                stmt_line.payee = payee_iban
        elif event["eventType"] == "PAYMENT_INBOUND_CREDIT_CARD":
            stmt_line.trntype = "XFER"
            stmt_line.memo = "Credit Card Payment"
            for section in event["details"]["sections"]:
                if section["title"] == "Übersicht":
                    for datum in section["data"]:
                        if datum["title"] == "Zahlung":
                            stmt_line.memo += " " + datum["detail"]["text"]
        elif event["eventType"] in ("INTEREST_PAYOUT", "INTEREST_PAYOUT_CREATED"):
            stmt_line.trntype = "INT"
            stmt_line.memo = "Interest Payout"
        elif event["eventType"] == "ssp_corporate_action_invoice_cash":
            stmt_line.trntype = "DIV"
        elif event["eventType"] in ("SAVINGS_PLAN_INVOICE_CREATED", "benefits_saveback_execution"):
            stmt_line.trntype = "BUYSTOCK"
            stmt_line.trntype_detailed = "BUY"
            if event["eventType"] == "SAVINGS_PLAN_INVOICE_CREATED":
                stmt_line.memo = "Savings Plan Execution"
            elif event["eventType"] == "benefits_saveback_execution":
                stmt_line.memo = "Saveback Execution"
            stmt_line.memo += " - " + event["title"]
            for section in event["details"]["sections"]:
                if section["title"].startswith("Du hast") and section["title"].endswith("investiert"):
                    stmt_line.security_id = section["action"]["payload"]
                elif section["title"].startswith("Dein Bonus von") and section["title"].endswith("wurde investiert"):
                    stmt_line.security_id = section["action"]["payload"]
                elif section["title"] == "Transaktion":
                    for datum in section["data"]:
                        if datum["title"] in ("Anteile", "Aktien"):
                            stmt_line.units = Decimal(datum["detail"]["text"].replace(',', '.'))
                        elif datum["title"] in ("Anteilspreis", "Aktienkurs"):
                            stmt_line.unit_price = Decimal(datum["detail"]["text"].replace(',', '.').split("\xa0")[0])
                        elif datum["title"] == "Gesamt":
                            stmt_line.amount = -Decimal(datum["detail"]["text"].replace(',', '.').split("\xa0")[0])
        return stmt_line


class TradeRepublicPlugin(Plugin):
    """Trade Republic plugin. Expects (possibly filtered) transactions from pytr transactions.csv or all_events.json: https://github.com/pytr-org/pytr"""

    def get_parser(self, filename: str) -> Union[TradeRepublicJsonParser, TradeRepublicCsvParser]:
        if filename.endswith(".csv"):
            fin = open(filename, "r")
            return TradeRepublicCsvParser(fin)
        elif filename.endswith(".json"):
            fin = open(filename, "r")
            return TradeRepublicJsonParser(fin)