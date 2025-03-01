# ofxstatement-traderepublic

This project provides a plugin for ofxstatement to parse Trade Republic
transaction statements. Trade Republic does not offer an official way to
export transactions, but the [pytr](https://github.com/pytr-org/pytr) project
provides a way to download transactions from the Trade Republic API. This
plugin can be used to convert the downloaded transactions from `pytr` to OFX
format.

## Installation

### From PyPI
```
pip install ofxstatement-traderepublic
```

### From github
```
git clone https://github.com/alson/ofxstatement-traderepublic.git
cd ofxstatement-traderepublic
pip install .
```

## Usage

This plugin will accept either a `transactions.csv` or `all_events.json`
from `pytr`. The JSON file provides more information, like the other
account number for bank transfers, or the exchange rate for FX
transactions. But the CSV file is easier to filter by date since `pytr`
does not allow filtering transactions from a certain time period:
```
(head -n 1 transactions.csv;grep '^2025-02-' transactions.csv | sort) > transactions-2025-02.csv
```

And then use `transactions-2025-02.csv` as input for the plugin.
