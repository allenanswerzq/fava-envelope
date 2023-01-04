from typing import NamedTuple, Any, List
from collections import OrderedDict
from beancount.core import data
from beancount.core.number import Decimal

BudgetTreeNode = NamedTuple(
    'BudgetTreeNode', [
        ('name', str),
        ('budget', Any),
        ('actual', Any)])

class BudgetTree:
    def __init__(self, n="root", b=None, a=None) -> None:
        self.node_ = BudgetTreeNode(name=n, budget=b, actual=a)
        # TODO: make order stable
        self.children_ = set()
        self.visit_ = set()
        self.node_map_ = {}

    def add_children(self, child):
        self.children_.add(child)

    def __getitem__(self, i):
        # For test purpose
        return list(self.children_)[i]

    def _dfs(self, post=None, pre=None):
        k = id(self)
        assert k not in self.visit_
        self.visit_.add(k)

        if pre:
            pre(self)

        for c in self.children_:
            c.dfs(post=post, pre=pre)

        if post:
            post(self)

    def dfs(self, post=None, pre=None):
        self.visit_.clear()
        self._dfs(post=post, pre=pre)

    def summarize(self):
        node_sum = {}
        def post(n : BudgetTree):
            tot_budget = 0
            if n.node_.budget: tot_budget += float(n.node_.budget)

            tot_actual = 0
            if n.node_.actual: tot_actual += float(n.node_.actual)

            for c in n.children_:
                tot_budget += node_sum[c][0]
                tot_actual += node_sum[c][1]

            tot_budget = Decimal(tot_budget).quantize(Decimal("0.00"))
            tot_actual = Decimal(tot_actual).quantize(Decimal("0.00"))

            node_sum[n] = (tot_budget, tot_actual)
            n.node_ = n.node_._replace(budget=str(tot_budget))
            n.node_ = n.node_._replace(actual=str(tot_actual))

        self.dfs(post=post)

    def parse_entries(self, entries):
        for e in entries:
            if isinstance(e, data.Custom) and e.values[0].value in ("allocate", "task"):
                self.add_children(self._parse_entry(e))

    def _create_or_get(self, task, n):
        # NOTE: for the same expenses, if task if different, we allocate
        # different nodes
        f = task + n
        if f not in self.node_map_:
            self.node_map_[f] = BudgetTree(n=n)
        return self.node_map_[f]

    def _parse_entry(self, e):
        vals = [x.value for x in e.values[1:]]
        assert len(vals) >= 2, "allocate A 100"

        # Use month to create the first node
        month = str(e.date)[0:-3]
        first = "monthly"
        if e.values[0].value == "task":
            # TODO: This is a Task budget, counted in both month budget and task
            # budget, find txns with same link or tag to count the actual
            first = "tasks"
        else:
            # Add month to be first node
            vals.insert(0, month)

        budget = float(vals[-1])

        ans = [ self._create_or_get(first, first) ]
        for i, k in enumerate(vals):
            if i == len(vals) - 1:
                ans[-1].node_ = ans[-1].node_._replace(budget=str(budget))
                break
            cur = self._create_or_get(first + month, k)
            ans[-1].add_children(cur)
            ans.append(cur)

        # for x in ans:
        #     print(x.node_, x, x.children_)

        return ans[0]

    def change_actual(self, month, n, v):
        for p in ("monthly", "tasks"):
            f = p + month + n
            if f in self.node_map_:
                changed = self.node_map_[f].node_._replace(actual=str(v))
                self.node_map_[f].node_ = changed
                return

        # assert False, f"{month} {n}"

    def pretty_output(self):
        level = {}
        level[self] = 0
        def pre(n : BudgetTree):
            for c in n.children_:
                level[c] = level[n] + 1
        self.dfs(pre=pre)

        def pretty(n : BudgetTree):
            f = "  " * level[n]
            print(f"{f} {n.node_.name} {n.node_.budget} | {n.node_.actual}")
        self.dfs(pre=pretty)

    def sankey_output(self):
        def pre(n: BudgetTree):
            if len(n.children_) == 0:
                print(f"{n.node_.name} [{n.node_.budget}] Budget")
                print(f"{n.node_.name} [{n.node_.actual}] Actual")
            else:
                for c in n.children_:
                    t = float(c.node_.budget) + float(c.node_.actual)
                    print(f"{n.node_.name} [{t}] {c.node_.name}")

        self.dfs(pre=pre)

def test_basic():
    root = BudgetTree()
    root.add_children(BudgetTree("month-1"))
    root[0].add_children(BudgetTree("expenses:food", "100", "120"))
    root[0].add_children(BudgetTree("expenses:shop", "200", "220"))

    root.add_children(BudgetTree("month-2"))
    root[1].add_children(BudgetTree("expenses:food", "300", "320"))
    root[1].add_children(BudgetTree("expenses:shop", "400", "420"))

    root.summarize()
    root.pretty_output()

def test_parse():
    raw = """
2022-12-01 custom "envelope" "allocate" "Expenses:Food:Shop"                10
2022-12-01 custom "envelope" "allocate" "Expenses:Food:Restaurants"         50
2022-12-01 custom "envelope" "allocate" "S" "Expenses:Housing:Rent"         30
2022-12-01 custom "envelope" "allocate" "S" "Expenses:Personal:Hair"        30
2022-12-01 custom "envelope" "allocate" "S" "T" "Expenses:Personal:Sport"   40
2022-12-01 custom "envelope" "allocate" "S1" "T1" "Expenses:Insurance"      40

2022-12-01 custom "envelope" "task" "task-name" "hardware" "Expenses:CPU"  40
2022-12-01 custom "envelope" "task" "task-name" "hardware" "Expenses:Memory"  40

2023-01-01 custom "envelope" "allocate" "Expenses:Food:Shop"                10
2023-01-01 custom "envelope" "allocate" "Expenses:Food:Restaurants"         50
"""
    from beancount.loader import load_string
    entries, errors, options_map = load_string(raw)
    assert len(entries) == 10
    # print(entries)
    root = BudgetTree()
    root.parse_entries(entries)
    root.summarize()
    root.pretty_output()
    root.sankey_output()


if __name__ == "__main__":
    # test_basic()
    test_parse()