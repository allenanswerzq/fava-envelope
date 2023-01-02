# Debug
from __future__ import annotations

import collections
import datetime
import logging
import re

import pandas as pd
from beancount.core import account_types
from beancount.core import amount
from beancount.core import convert
from beancount.core import data
from beancount.core import inventory
from beancount.core import prices
from beancount.core.data import Custom
from beancount.core.number import Decimal
from beancount.parser import options
from beancount.query import query
from dateutil.relativedelta import relativedelta
from fava_envelope.modules import budget_tree


class BeancountEnvelope:
    def __init__(self, entries, options_map, currency, date_start, date_end):

        self.entries = entries
        self.options_map = options_map
        self.currency = currency
        self.negative_rollover = False
        self.months_ahead = 0
        self.tree = budget_tree.BudgetTree()

        if self.currency:
            self.etype = "envelope" + self.currency
        else:
            self.etype = "envelope"

        (  _,
           self.budget_accounts,
           self.mappings,
           self.income_accounts,
           self.months_ahead,
        ) = self._find_envelop_settings()

        if not self.currency:
            self.currency = self._find_currency(options_map)

        decimal_precison = "0.00"
        self.Q = Decimal(decimal_precison)
        self.price_map = prices.build_price_map(entries)
        self.acctypes = options.get_account_types(options_map)

        self.date_start = date_start
        self.date_end = date_end

        assert self.date_start
        assert self.date_end


    def _find_currency(self, options_map):
        default_currency = "USD"
        opt_currency = options_map.get("operating_currency")
        currency = opt_currency[0] if opt_currency else default_currency
        if len(currency) == 3:
            return currency

        logging.warning(
            f"invalid operating currency: {currency},"
            + "defaulting to {default_currency}"
        )
        return default_currency

    def _find_envelop_settings(self):
        start_date = None
        budget_accounts = []
        mappings = []
        income_accounts = []
        months_ahead = 0

        for e in self.entries:
            if isinstance(e, Custom) and e.type == self.etype:
                if e.values[0].value == "start date":
                    start_date = e.values[1].value
                if e.values[0].value == "budget account":
                    budget_accounts.append(re.compile(e.values[1].value))
                if e.values[0].value == "mapping":
                    map_set = (
                        re.compile(e.values[1].value),
                        e.values[2].value,
                    )
                    mappings.append(map_set)
                if e.values[0].value == "income account":
                    income_accounts.append(re.compile(e.values[1].value))
                if e.values[0].value == "currency":
                    self.currency = e.values[1].value
                if e.values[0].value == "negative rollover":
                    if e.values[1].value == "allow":
                        self.negative_rollover = True
                if e.values[0].value == "months ahead":
                    months_ahead = int(e.values[1].value)
        return (
            start_date,
            budget_accounts,
            mappings,
            income_accounts,
            months_ahead,
        )

    def _fill_budget_tree(self):
        self.tree.parse_entries(self.entries)
        for index, row in self.envelope_df.iterrows():
            actual = row["activity"]
            name = row.name
            if actual != 0:
                self.tree.change_actual(name, actual)
        self.tree.summarize()
        self.tree.pretty_output()

    def envelope_tables(self):
        self.income_df = pd.DataFrame(columns=["Column1"])
        self.envelope_df = pd.DataFrame(columns=["budgeted", "activity", "available"])
        self.envelope_df.index.name = "Envelopes"

        self._calculate_budget_activity()
        self._calc_budget_budgeted()

        # Calculate Starting Balance Income
        starting_balance = Decimal(0.0)
        query_str = (
            f"select account, convert(sum(position),'{self.currency}')"
            + f" from close on {str(self.date_start)} group by 1 order by 1;"
        )
        rows = query.run_query(
            self.entries, self.options_map, query_str, numberify=True
        )

        for row in rows[1]:
            if any(regexp.match(row[0]) for regexp in self.budget_accounts):
                if row[1] is not None:
                    starting_balance += row[1]

        self.income_df.loc["Avail Income"] += starting_balance
        self.envelope_df.fillna(Decimal(0.00), inplace=True)

        # Set available
        for index, row in self.envelope_df.iterrows():
            row["available"] = (row["budgeted"] + row["activity"])

        # print(self.envelope_df)

        # Set overspent
        overspent = Decimal(0)
        for _, row in self.envelope_df.iterrows():
            if row["available"] < Decimal(0.00):
                overspent += Decimal(row["available"])
        self.income_df.loc["Overspent"] = -overspent

        # Set Budgeted for month
        self.income_df.loc["Budgeted"] = Decimal(self.envelope_df["budgeted"].sum())
        self.income_df.loc["Activity"] = Decimal(self.envelope_df["activity"].sum())
        self.income_df.loc["Available"] = Decimal(self.envelope_df["available"].sum())

        self._fill_budget_tree()

        # print(self.income_df)
        # print(self.envelope_df)
        return self.income_df, self.envelope_df, self.currency

    def _calculate_budget_activity(self):

        # Accumulate expenses for the period
        balances = collections.defaultdict(inventory.Inventory)
        for entry in data.filter_txns(self.entries):

            # Check entry in date range
            if entry.date < self.date_start or entry.date > self.date_end:
                continue

            contains_budget_accounts = False
            for posting in entry.postings:
                if any(regexp.match(posting.account) for regexp in self.budget_accounts):
                    contains_budget_accounts = True
                    break

            if not contains_budget_accounts:
                continue

            for posting in entry.postings:

                account = posting.account
                for regexp, target_account in self.mappings:
                    if regexp.match(account):
                        account = target_account
                        break

                account_type = account_types.get_account_type(account)
                if posting.units.currency != self.currency:
                    orig = posting.units.number
                    if posting.price is not None:
                        converted = posting.price.number * orig
                        posting = data.Posting(
                            posting.account,
                            amount.Amount(converted, self.currency),
                            posting.cost,
                            None,
                            posting.flag,
                            posting.meta,
                        )
                    else:
                        continue

                if account_type == self.acctypes.income or (
                    any(regexp.match(account) for regexp in self.income_accounts)
                ):
                    account = "Income"
                elif any(regexp.match(posting.account) for regexp in self.budget_accounts):
                    continue
                # TODO WARn of any assets / liabilities left

                balances[account].add_position(posting)

        # print(balances)

        # Reduce the final balances to numbers
        sbalances = collections.defaultdict()
        for account, balance in sorted(balances.items()):
            balance = balance.reduce(convert.get_value, self.price_map)
            balance = balance.reduce(convert.convert_position, self.currency, self.price_map)
            try:
                pos = balance.get_only_position()
            except AssertionError:
                print(balance)
                raise
            total = pos.units.number if pos and pos.units else None
            sbalances[account] = total

        self.income_df.loc["Avail Income"] = Decimal(0.00)

        for account in sorted(sbalances.keys()):
            total = sbalances[account]
            temp = total.quantize(self.Q) if total else 0.00
            # swap sign to be more human readable
            temp *= -1

            if account == "Income":
                self.income_df.loc["Avail Income"] = Decimal(temp)
            else:
                self.envelope_df.loc[account, "budgeted"] = Decimal(0.00)
                self.envelope_df.loc[account, "activity"] = Decimal(temp)
                self.envelope_df.loc[account, "available"] = Decimal(0.00)

    def _calc_budget_budgeted(self):
        for e in self.entries:
            if isinstance(e, Custom) and e.type == self.etype:

                # Check entry in date range
                if e.date < self.date_start or e.date > self.date_end:
                    continue
                if e.values[0].value == "allocate":
                    self.envelope_df.loc[e.values[1].value, "budgeted"] = Decimal(e.values[2].value)

        # Remove no budgeted accounts
        rows_to_drop = []
        for index, row in self.envelope_df.iterrows():
            if row["budgeted"] == 0:
                rows_to_drop.append(index)

        self.envelope_df = self.envelope_df.drop(rows_to_drop)