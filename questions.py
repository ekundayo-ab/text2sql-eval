"""30 business questions with hand-written gold SQL (DuckDB).

kind:   lookup | aggregate | join | rule (needs a business rule from the catalog) | data (a data-quality case)
ordered: the row order is part of the answer
"""

REV = "i.qty * i.unit_price_cents - i.discount_cents"
PAID = "from orders o join order_items i using (order_id) where o.status = 'paid'"

QUESTIONS = [
    dict(id="q01", kind="lookup", q="How many stores does the chain have?",
         gold="select count(*) from stores"),
    dict(id="q02", kind="lookup", q="How many products are in the Kitchen category?",
         gold="select count(*) from products where category = 'Kitchen'"),
    dict(id="q03", kind="rule", q="How many customers live in Munich?",
         gold="select count(*) from customers where city = 'München' and deleted_at is null"),
    dict(id="q04", kind="rule", q="What was the total revenue in euros in September 2026?",
         gold=f"select round(sum({REV}) / 100, 2) {PAID} and o.ordered_at >= '2026-09-01' and o.ordered_at < '2026-10-01'"),
    dict(id="q05", kind="aggregate", q="How many orders were cancelled in 2025?",
         gold="select count(*) from orders where status = 'cancelled' and year(ordered_at) = 2025"),
    dict(id="q06", kind="rule", q="What was revenue in euros per sales channel in 2025?",
         gold=f"select o.channel, round(sum({REV}) / 100, 2) {PAID} and year(o.ordered_at) = 2025 group by 1"),
    dict(id="q07", kind="join", ordered=True, q="Which 4 products sold the most units in 2026? Give the product id, name and units, highest first.",
         gold=f"select p.product_id, p.name, sum(i.qty) as units {PAID.replace('using (order_id)', 'using (order_id) join products p using (product_id)')} "
              "and year(o.ordered_at) = 2026 group by 1, 2 order by units desc, p.product_id limit 4"),
    dict(id="q08", kind="join", q="Which store city had the highest revenue in the third quarter of 2026?",
         gold=f"select s.city {PAID.replace('using (order_id)', 'using (order_id) join stores s using (store_id)')} "
              "and o.ordered_at >= '2026-07-01' and o.ordered_at < '2026-10-01' group by 1 order by sum(i.qty * i.unit_price_cents - i.discount_cents) desc limit 1"),
    dict(id="q09", kind="rule", q="What was the average order value in euros of online orders in 2026?",
         gold=f"select round(sum({REV}) / 100 / count(distinct o.order_id), 2) {PAID} and o.channel = 'online' and year(o.ordered_at) = 2026"),
    dict(id="q10", kind="aggregate", q="How many customers placed their first paid order in 2026?",
         gold="select count(*) from (select customer_id, min(ordered_at) as first from orders where status = 'paid' group by 1) where year(first) = 2026"),
    dict(id="q11", kind="rule", q="What was net revenue in euros in October 2026, after refunds?",
         gold=f"select round(((select sum({REV}) {PAID} and o.ordered_at >= '2026-10-01' and o.ordered_at < '2026-11-01') "
              "- (select coalesce(sum(refund_cents), 0) from returns where returned_at >= '2026-10-01' and returned_at < '2026-11-01')) / 100, 2)"),
    dict(id="q12", kind="join", q="For paid orders placed in 2026, what fraction of the units sold in each product category was returned? Give category and fraction.",
         gold="with sold as (select p.category, sum(i.qty) as s from orders o join order_items i using (order_id) join products p using (product_id) "
              "where o.status = 'paid' and year(o.ordered_at) = 2026 group by 1), "
              "ret as (select p.category, sum(r.qty) as r from returns r join orders o using (order_id) join products p on p.product_id = r.product_id "
              "where year(o.ordered_at) = 2026 group by 1) "
              "select category, round(coalesce(r, 0) / s, 4) from sold left join ret using (category)"),
    dict(id="q13", kind="join", q="Which product category had the highest refunds in euros for returns made in 2025?",
         gold="select p.category from returns r join products p using (product_id) where year(r.returned_at) = 2025 group by 1 order by sum(r.refund_cents) desc limit 1"),
    dict(id="q14", kind="aggregate", q="How many paid orders had at least one discounted line?",
         gold=f"select count(distinct o.order_id) {PAID} and i.discount_cents > 0"),
    dict(id="q15", kind="rule", ordered=True, q="What was revenue in euros for each month of 2026? Give the month number (1 to 12) and revenue, in month order.",
         gold=f"select month(o.ordered_at) as m, round(sum({REV}) / 100, 2) {PAID} and year(o.ordered_at) = 2026 group by 1 order by 1"),
    dict(id="q16", kind="rule", q="How many customers who signed up in 2025 have never placed a paid order?",
         gold="select count(*) from customers c where year(c.signup_date) = 2025 and c.deleted_at is null "
              "and not exists (select 1 from orders o where o.customer_id = c.customer_id and o.status = 'paid')"),
    dict(id="q17", kind="rule", q="On paid orders in 2026, what was the total discount as a percentage of the undiscounted line value?",
         gold=f"select round(100.0 * sum(i.discount_cents) / sum(i.qty * i.unit_price_cents), 2) {PAID} and year(o.ordered_at) = 2026"),
    dict(id="q18", kind="join", q="How many products that are no longer offered were still sold on paid orders in 2026?",
         gold=f"select count(distinct i.product_id) {PAID.replace('using (order_id)', 'using (order_id) join products p using (product_id)')} "
              "and year(o.ordered_at) = 2026 and not p.is_active"),
    dict(id="q19", kind="rule", q="For product 17, how many euros is its list price above the average price customers actually paid per unit on paid orders, weighted by quantity?",
         gold=f"select round((select list_price_cents from products where product_id = 17) / 100.0 - sum(i.qty * i.unit_price_cents) / sum(i.qty) / 100, 2) {PAID} and i.product_id = 17"),
    dict(id="q20", kind="rule", q="What percentage of 2026 revenue came from online orders?",
         gold=f"select round(100.0 * sum(case when o.channel = 'online' then {REV} end) / sum({REV}), 2) {PAID} and year(o.ordered_at) = 2026"),
    dict(id="q21", kind="join", q="Which store city had the most cancelled orders?",
         gold="select s.city from orders o join stores s using (store_id) where o.status = 'cancelled' group by 1 order by count(*) desc limit 1"),
    dict(id="q22", kind="aggregate", q="How many customers have paid orders both online and in a store?",
         gold="select count(*) from (select customer_id from orders where status = 'paid' group by 1 having count(distinct channel) = 2)"),
    dict(id="q23", kind="rule", ordered=True, q="Which 3 customers had the highest net revenue in 2026 (paid orders placed in 2026 minus refunds made in 2026 on their orders)? Give customer ids, highest first.",
         gold=f"with rev as (select o.customer_id, sum({REV}) as r {PAID} and year(o.ordered_at) = 2026 group by 1), "
              "ref as (select o.customer_id, sum(x.refund_cents) as f from returns x join orders o using (order_id) where year(x.returned_at) = 2026 group by 1) "
              "select customer_id from rev left join ref using (customer_id) order by r - coalesce(f, 0) desc, customer_id limit 3"),
    dict(id="q24", kind="aggregate", q="What was the average number of units per paid order in 2025?",
         gold=f"select round(sum(i.qty) / count(distinct o.order_id), 2) {PAID} and year(o.ordered_at) = 2025"),
    dict(id="q25", kind="aggregate", q="In which month of 2025 (1 to 12) were the most returns made?",
         gold="select month(returned_at) from returns where year(returned_at) = 2025 group by 1 order by count(*) desc limit 1"),
    dict(id="q26", kind="rule", q="How much revenue in euros did 2026 orders bring from customers who have since deleted their account?",
         gold=f"select round(sum({REV}) / 100, 2) {PAID.replace('using (order_id)', 'using (order_id) join customers c using (customer_id)')} "
              "and year(o.ordered_at) = 2026 and c.deleted_at is not null"),
    dict(id="q27", kind="data", q="How many orders have no items at all?",
         gold="select count(*) from orders o where not exists (select 1 from order_items i where i.order_id = o.order_id)"),
    dict(id="q28", kind="rule", q="Which cities have more than 200 customers?",
         gold="select city from customers where deleted_at is null group by 1 having count(*) > 200"),
    dict(id="q29", kind="data", q="How many products have never been ordered, in any order status?",
         gold="select count(*) from products p where not exists (select 1 from order_items i where i.product_id = p.product_id)"),
    dict(id="q30", kind="rule", q="What was the largest single refund in euros?",
         gold="select round(max(refund_cents) / 100, 2) from returns"),
]
