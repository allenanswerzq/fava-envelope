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
    def __init__(self, filtered, options_map, currency, date_start, date_end):

        self.entries = filtered.ledger.all_entries
        self.options_map = options_map
        self.currency = currency
        self.negative_rollover = False
        self.months_ahead = 0
        self.tree = budget_tree.BudgetTree()

        if self.currency:
            self.etype = "envelope" + self.currency
        else:
            self.etype = "envelope"

        (  start_date,
           self.budget_accounts,
           self.mappings,
           self.income_accounts,
           self.months_ahead,
        ) = self._find_envelop_settings()

        if not self.currency:
            self.currency = self._find_currency(options_map)

        decimal_precison = "0.00"
        self.Q = Decimal(decimal_precison)

        today = datetime.date.today()
        self.date_start = datetime.datetime.strptime(start_date, "%Y-%m").date()
        self.date_end = datetime.date(today.year, today.month, today.day) + relativedelta(months=+self.months_ahead)

        self.price_map = prices.build_price_map(self.entries)
        self.acctypes = options.get_account_types(options_map)

        assert self.date_start
        assert self.date_end


    def _find_currency(self, options_map):
        default_currency = "USD"
        opt_currency = options_map.get("operating_currency")
        currency = opt_currency[0] if opt_currency else default_currency
        if len(currency) == 3:
            return currency

        logging.warning(
            f"invalid operating currency: {currency}, defaulting to {default_currency}"
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
                if e.values[0].value == "self.months_ ahead":
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
        for i, row in self.envelope_df.iterrows():
            for month in self.months_:
                k = (month, "activity")
                if k not in row: continue
                actual = row[month, "activity"]
                name = row.name
                if not actual.is_nan():
                    self.tree.change_actual("monthly", month, name, actual)

        for i, row in self.year_actual.iterrows():
            for year in self.years_:
                # NOTE: year budget must be created at the first month of a year
                month = year.split("-")[1] + "-01"
                actual = Decimal(row[year])
                name = row.name
                if not actual.is_nan():
                    self.tree.change_actual("tasks", month, name, actual)

        self.tree.summarize()
        self.tree.pretty_output()
        # self.tree.sankey_output()

    def _get_months(self):
        self.months_ = []
        date_current = self.date_start
        while date_current < self.date_end:
            self.months_.append(
                f"{date_current.year}-{str(date_current.month).zfill(2)}"
            )
            month = date_current.month - 1 + 1
            year = date_current.year + month // 12
            month = month % 12 + 1
            date_current = datetime.date(year, month, 1)
        return self.months_

    def _set_available(self):
        for i, row in self.envelope_df.iterrows():
            for index2, month in enumerate(self.months_):
                if month not in row: continue
                row[month, "available"] = Decimal(row[month, "budgeted"]) + Decimal(row[month, "activity"])
                # if index2 == 0:
                #     row[month, "available"] = row[month, "budgeted"] + row[month, "activity"]
                # else:
                #     if (self.months_[index2 - 1], "available") not in row: continue
                #     prev_available = row[self.months_[index2 - 1], "available"]
                #     if prev_available > 0 or self.negative_rollover:
                #         row[month, "available"] = (
                #             prev_available
                #             + row[month, "budgeted"]
                #             + row[month, "activity"]
                #         )
                #     else:
                #         row[month, "available"] = (
                #             row[month, "budgeted"] + row[month, "activity"]
                #         )

    def _set_start_balance(self):
        # Calculate Starting Balance Income
        starting_balance = Decimal(0.0)
        query_str = (
            f"select account, convert(sum(position),'{self.currency}')"
            + f" from close on {self.months_[0]}-01 group by 1 order by 1;"
        )
        rows = query.run_query(
            self.entries, self.options_map, query_str, numberify=True)

        for row in rows[1]:
            if any(regexp.match(row[0]) for regexp in self.budget_accounts):
                if row[1] is not None:
                    starting_balance += row[1]

        self.income_df[self.months_[0]]["Avail Income"] += starting_balance

    def _set_overspent(self):
        overspent = Decimal(0)
        for index, month in enumerate(self.months_):
            if index == 0:
                self.income_df.loc["Overspent", month] = Decimal(0.00)
            else:
                overspent = Decimal(0.00)
                for index2, row in self.envelope_df.iterrows():
                    cur = (self.months_[index - 1], "available")
                    if cur in row and row[cur] < Decimal(0.00):
                        overspent += Decimal(row[cur])
                self.income_df.loc["Overspent", month] = overspent

    def _set_extra(self):
        # Set Budgeted for month
        for month in self.months_:
            if (month, "budgeted") in self.envelope_df:
                self.income_df.loc["Budgeted", month] = Decimal(
                    -1 * self.envelope_df[month, "budgeted"].sum()
                )

        # Adjust Avail Income
        # for index, month in enumerate(self.months_):
        #     if index == 0:
        #         continue
        #     else:
        #         prev_month = self.months_[index - 1]
        #         self.income_df.loc["Avail Income", month] = (
        #             self.income_df.loc["Avail Income", month]
        #             + self.income_df.loc["Avail Income", prev_month]
        #             + self.income_df.loc["Overspent", prev_month]
        #             + self.income_df.loc["Budgeted", prev_month]
        #         )

        # # Set Budgeted in the future
        # for index, month in enumerate(self.months_):
        #     sum_total = self.income_df[month].sum()
        #     if (index == len(self.months_) - 1) or sum_total < 0:
        #         self.income_df.loc["Budgeted Future", month] = Decimal(0.00)
        #     else:
        #         next_month = self.months_[index + 1]
        #         opp_budgeted_next_month = (
        #             self.income_df.loc["Budgeted", next_month] * -1
        #         )
        #         if opp_budgeted_next_month < sum_total:
        #             self.income_df.loc["Budgeted Future", month] = Decimal(
        #                 -1 * opp_budgeted_next_month
        #             )
        #         else:
        #             self.income_df.loc["Budgeted Future", month] = Decimal(
        #                 -1 * sum_total
        #             )

        # # Set to be budgeted
        # for index, month in enumerate(self.months_):
        #     self.income_df.loc["To Be Budgeted", month] = Decimal(
        #         self.income_df[month].sum()
        #     )

    def _get_years(self):
        ans = set()
        for m in self.months_:
            ans.add("budget-" + str(m).split("-")[0])
        return list(ans)

    def envelope_tables(self):
        self.months_ = self._get_months()
        self.years_ = self._get_years()
        # Create Income DataFrame
        self.income_df = pd.DataFrame(columns=self.months_)
        self.year_actual = pd.DataFrame(columns=self.years_)

        # Create Envelopes DataFrame
        column_index = pd.MultiIndex.from_product(
            [self.months_, ["budgeted", "activity", "available"]],
            names=["Month", "col"],)
        self.envelope_df = pd.DataFrame(columns=column_index)
        self.envelope_df.index.name = "Envelopes"
        self.envelope_df.fillna(Decimal(0.00), inplace=True)

        # TODO: add task data frame to count task budget

        self._calculate_budget_activity()
        self._calc_budget_budgeted()
        self._set_start_balance()
        self._set_available()
        self._set_overspent()
        self._set_extra()
        self._fill_budget_tree()

        # print(self.income_df)
        # print(self.envelope_df)
        return self.income_df, self.envelope_df, self.currency

    def _calculate_budget_activity(self):
        # Accumulate expenses for the period
        balances = collections.defaultdict(
            lambda: collections.defaultdict(inventory.Inventory)
        )
        all_months = set()
        for entry in data.filter_txns(self.entries):

            # Check entry in date range
            if entry.date < self.date_start or entry.date > self.date_end:
                continue

            month = (entry.date.year, entry.date.month)
            # TODO domwe handle no transaction in a month?
            all_months.add(month)

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

                balances[account][month].add_position(posting)

        # print(balances)

        # Reduce the final balances to numbers
        sbalances = collections.defaultdict(dict)
        for account, months in sorted(balances.items()):
            for month, balance in sorted(months.items()):
                year, mth = month
                date = datetime.date(year, mth, 1)
                balance = balance.reduce(
                    convert.get_value, self.price_map, date
                )
                balance = balance.reduce(
                    convert.convert_position,
                    self.currency,
                    self.price_map,
                    date,
                )
                try:
                    pos = balance.get_only_position()
                except AssertionError:
                    print(balance)
                    raise
                total = pos.units.number if pos and pos.units else None
                sbalances[account][month] = total

        # Pivot the table
        self.income_df.loc["Avail Income", :] = Decimal(0.00)

        for account in sorted(sbalances.keys()):
            for month in sorted(all_months):
                total = sbalances[account].get(month, None)
                temp = total.quantize(self.Q) if total else 0.00
                # swap sign to be more human readable
                temp *= -1

                m = f"{str(month[0])}-{str(month[1]).zfill(2)}"
                if account == "Income":
                    self.income_df.loc["Avail Income", m] = Decimal(temp)
                else:
                    self.envelope_df.loc[account, (m, "budgeted")] = Decimal(0.00)
                    self.envelope_df.loc[account, (m, "activity")] = Decimal(temp)
                    self.envelope_df.loc[account, (m, "available")] = Decimal(0.00)

                    year_ss = "budget-" + str(month[0])
                    if (account, year_ss) in self.year_actual:
                        self.year_actual.loc[account, year_ss] += Decimal(temp)
                    else:
                        self.year_actual.loc[account, year_ss] = Decimal(temp)

        # print(self.envelope_df)

    def _calc_budget_budgeted(self):
        for e in self.entries:
            if isinstance(e, Custom) and e.type == self.etype:
                # Check entry in date range
                if e.date < self.date_start or e.date > self.date_end:
                    continue

                if e.values[0].value == "allocate":
                    month = f"{e.date.year}-{e.date.month:02}"
                    vals = [x.value for x in e.values]
                    self.envelope_df.loc[vals[-2], (month, "budgeted")] = Decimal(vals[-1])

        # First drop all months that have no budget
        months_to_drop = []
        for month in self.months_:
            if self.envelope_df[month, "budgeted"].sum() == 0:
                months_to_drop.append(month)
        self.envelope_df = self.envelope_df.drop(months_to_drop, axis=1)
        self.envelope_df.fillna(Decimal(0.00), inplace=True)

        # print(self.envelope_df)