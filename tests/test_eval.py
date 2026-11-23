"""Checks the harness itself, with no model calls: python -m unittest discover -s tests"""

import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent))
from build_db import build  # noqa: E402
from questions import QUESTIONS  # noqa: E402
from t2s import Retriever, extract_sql, prompt_for, run_sql, same_result, schema_text  # noqa: E402


class Scoring(unittest.TestCase):
    def test_same_rows_any_order(self):
        self.assertTrue(same_result([("a", 1), ("b", 2)], [("b", 2.0), ("a", 1)]))

    def test_order_matters_when_asked(self):
        self.assertFalse(same_result([("a", 1), ("b", 2)], [("b", 2), ("a", 1)], ordered=True))

    def test_extra_columns_allowed_missing_not(self):
        self.assertTrue(same_result([("München",)], [(3, "münchen", 99.5)]))
        self.assertFalse(same_result([("München", 5)], [("München",)]))

    def test_money_within_a_cent(self):
        self.assertTrue(same_result([(1234.56,)], [(1234.555,)]))
        self.assertFalse(same_result([(1234.56,)], [(123456,)]), "cents are not euros")

    def test_row_count_must_match(self):
        self.assertFalse(same_result([(1,)], [(1,), (1,)]))
        self.assertFalse(same_result([(1,)], None))

    def test_sql_extraction(self):
        self.assertEqual(extract_sql("Here:\n```sql\nselect 1;\n```"), "select 1")
        self.assertEqual(extract_sql("no code"), "")


class Gold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = str(Path(cls.tmp.name) / "shop.duckdb")
        build(path)
        cls.con = duckdb.connect(path, read_only=True)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    def test_every_gold_query_runs_and_answers(self):
        for q in QUESTIONS:
            with self.subTest(q["id"]):
                rows, err = run_sql(self.con, q["gold"])
                self.assertEqual(err, "")
                self.assertTrue(rows, "empty gold answer")
                self.assertTrue(all(v is not None for r in rows for v in r), "NULL in a gold answer")

    def test_single_answers_have_no_tie(self):
        # "which X had the most Y" is only fair if the runner-up is behind
        for qid, sql in [("q08", "select s.city, sum(i.qty * i.unit_price_cents - i.discount_cents) v from orders o join order_items i using (order_id) join stores s using (store_id) where o.status = 'paid' and o.ordered_at >= '2026-07-01' and o.ordered_at < '2026-10-01' group by 1 order by 2 desc limit 2"),
                         ("q13", "select p.category, sum(r.refund_cents) from returns r join products p using (product_id) where year(r.returned_at) = 2025 group by 1 order by 2 desc limit 2"),
                         ("q21", "select s.city, count(*) from orders o join stores s using (store_id) where o.status = 'cancelled' group by 1 order by 2 desc limit 2"),
                         ("q25", "select month(returned_at), count(*) from returns where year(returned_at) = 2025 group by 1 order by 2 desc limit 2")]:
            with self.subTest(qid):
                (a, b) = self.con.execute(sql).fetchall()
                self.assertNotEqual(a[-1], b[-1])

    def test_top_n_has_no_tie_at_the_cut(self):
        for qid, sql in [("q07", "select sum(i.qty) u from orders o join order_items i using (order_id) where o.status = 'paid' and year(o.ordered_at) = 2026 group by i.product_id order by u desc limit 5"),
                         ("q23", "with rev as (select o.customer_id, sum(i.qty * i.unit_price_cents - i.discount_cents) r from orders o join order_items i using (order_id) where o.status = 'paid' and year(o.ordered_at) = 2026 group by 1), ref as (select o.customer_id, sum(x.refund_cents) f from returns x join orders o using (order_id) where year(x.returned_at) = 2026 group by 1) select r - coalesce(f, 0) from rev left join ref using (customer_id) order by 1 desc limit 4")]:
            with self.subTest(qid):
                vals = [r[0] for r in self.con.execute(sql).fetchall()]
                self.assertNotEqual(vals[-2], vals[-1], f"tie at the cut: {vals}")
                self.assertEqual(len(set(vals[:-1])), len(vals) - 1, f"tie inside the top: {vals}")

    def test_traps_change_the_answer(self):
        # each trap matters: the naive query gives a different number
        q = self.con.execute
        self.assertNotEqual(q("select count(*) from customers where city = 'München'").fetchone(),
                            q(QUESTIONS[2]["gold"]).fetchone(), "deleted customers")
        self.assertNotEqual(q("select sum(qty * unit_price_cents) from order_items join orders using (order_id) where year(ordered_at) = 2026").fetchone(),
                            q("select sum(qty * unit_price_cents) from order_items join orders using (order_id) where year(ordered_at) = 2026 and status = 'paid'").fetchone(),
                            "cancelled orders")

    def test_retrieval_finds_the_revenue_rule(self):
        r = Retriever()
        self.assertIn("r.revenue", [e["id"] for e in r.top("What was the total revenue in euros in September 2026?")])
        _, ids = prompt_for("How many customers live in Munich?", schema_text(self.con), "rag", r)
        self.assertEqual(len(ids), 6)


if __name__ == "__main__":
    unittest.main()
