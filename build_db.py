"""Builds shop.duckdb: a small German retail chain, generated from a fixed seed.

The data has the traps real company data has, each written down in catalog.json:
money in cents, cancelled and refunded orders that must not count as revenue,
soft-deleted customers, a current list price that is not the price paid,
online orders with no store, a handful of orders with no items, and returns.

Run: python build_db.py [path]   (default shop.duckdb)
"""

import random
import sys
from datetime import date, datetime, timedelta

import duckdb

SEED = 20261123
CITIES = ["München", "Berlin", "Hamburg", "Köln", "Frankfurt", "Stuttgart", "Leipzig", "Nürnberg"]
CATEGORIES = {
    "Kitchen": ["Pan", "Knife", "Kettle", "Grater", "Pot"],
    "Garden": ["Hose", "Shears", "Planter", "Rake", "Lamp"],
    "Bath": ["Towel", "Mat", "Mirror", "Shelf", "Basket"],
    "Office": ["Desk Lamp", "Chair Pad", "Organizer", "Notebook", "Stand"],
    "Toys": ["Puzzle", "Blocks", "Train", "Kite", "Doll"],
    "Outdoor": ["Tent", "Bottle", "Backpack", "Stool", "Torch"],
}
ADJ = ["Classic", "Nordic", "Pro", "Mini", "Eco", "Urban"]


def build(path: str) -> None:
    rnd = random.Random(SEED)
    con = duckdb.connect(path)
    for t in ["returns", "order_items", "orders", "products", "customers", "stores"]:
        con.execute(f"drop table if exists {t}")
    con.execute("""
        create table stores (store_id integer primary key, city varchar not null, opened_on date not null);
        create table customers (customer_id integer primary key, city varchar not null, signup_date date not null,
                                deleted_at timestamp);
        create table products (product_id integer primary key, name varchar not null, category varchar not null,
                               list_price_cents integer not null, is_active boolean not null);
        create table orders (order_id integer primary key, customer_id integer not null, store_id integer,
                             channel varchar not null, status varchar not null, ordered_at timestamp not null);
        create table order_items (order_id integer not null, product_id integer not null, qty integer not null,
                                  unit_price_cents integer not null, discount_cents integer not null);
        create table returns (return_id integer primary key, order_id integer not null, product_id integer not null,
                              qty integer not null, refund_cents integer not null, returned_at timestamp not null);
    """)

    stores = [(i + 1, c, date(2018 + i % 5, 1 + i, 1)) for i, c in enumerate(CITIES)]
    con.executemany("insert into stores values (?, ?, ?)", stores)

    customers = []
    for cid in range(1, 2001):
        city = rnd.choices(CITIES, weights=[30, 25, 15, 10, 8, 6, 3, 3])[0]
        signup = date(2024, 1, 1) + timedelta(days=rnd.randrange(0, 1000))
        deleted = datetime(2026, 1, 1) + timedelta(days=rnd.randrange(0, 290)) if rnd.random() < 0.06 else None
        customers.append((cid, city, signup, deleted))
    con.executemany("insert into customers values (?, ?, ?, ?)", customers)

    products = []
    pid = 0
    for cat, nouns in CATEGORIES.items():
        for noun in nouns:
            for adj in rnd.sample(ADJ, 4):
                pid += 1
                products.append((pid, f"{adj} {noun}", cat, rnd.choice([499, 999, 1499, 1999, 2999, 4999, 7999, 12999]),
                                 rnd.random() > 0.1))
    con.executemany("insert into products values (?, ?, ?, ?, ?)", products)

    orders, items, returns = [], [], []
    start = datetime(2025, 1, 1)
    span = int((datetime(2026, 11, 1) - start).total_seconds())
    rid = 0
    for oid in range(1, 15001):
        c = customers[rnd.randrange(len(customers))]
        ordered_at = start + timedelta(seconds=rnd.randrange(span))
        signup = datetime.combine(c[2], datetime.min.time())
        if ordered_at < signup:
            ordered_at = signup + timedelta(hours=rnd.randrange(1, 2000))
            if ordered_at >= datetime(2026, 11, 1):
                ordered_at = datetime(2026, 10, 31, 12)
        online = rnd.random() < 0.45
        store = None if online else rnd.choice(stores)[0]
        status = rnd.choices(["paid", "cancelled", "refunded"], weights=[88, 8, 4])[0]
        if oid % 997 == 0:
            status = "cancelled"  # the empty orders below were abandoned checkouts
        orders.append((oid, c[0], store, "online" if online else "store", status, ordered_at))
        if oid % 997 == 0:
            continue  # a few orders with no items: a data-quality case
        for p in rnd.sample(products, rnd.choice([1, 1, 2, 2, 3, 4])):
            qty = rnd.choice([1, 1, 1, 2, 2, 3])
            unit = int(p[3] * rnd.choice([1.0, 1.0, 0.9, 0.8, 1.05]))
            disc = rnd.choice([0, 0, 0, 0, 100, 250, 500]) if qty * unit > 1000 else 0
            items.append((oid, p[0], qty, unit, disc))
            if status == "paid" and rnd.random() < 0.06:
                rid += 1
                rq = rnd.randint(1, qty)
                returns.append((rid, oid, p[0], rq, rq * unit, ordered_at + timedelta(days=rnd.randint(2, 40))))
    con.executemany("insert into orders values (?, ?, ?, ?, ?, ?)", orders)
    con.executemany("insert into order_items values (?, ?, ?, ?, ?)", items)
    con.executemany("insert into returns values (?, ?, ?, ?, ?, ?)", returns)
    con.close()


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "shop.duckdb")
