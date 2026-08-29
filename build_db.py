"""
build_db.py
Loads SuperStoreOrders.csv, cleans it, and writes it into sales.db (SQLite).
Run this once (or whenever the CSV changes) before running agent.py.
"""

import pandas as pd
import sqlite3

CSV_PATH = "SuperStoreOrders.csv"   # put this .py file in the same folder as the CSV
DB_PATH = "sales.db"

def main():
    print(f"Reading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, encoding="latin-1")

    # Fix 1: 'sales' column has comma separators (e.g. "1,648") and is stored as text.
    # Strip commas and convert to float so SQL SUM/AVG/etc. work correctly.
    df["sales"] = df["sales"].astype(str).str.replace(",", "").astype(float)

    # Fix 2: dates are DD-MM-YYYY strings. SQLite has no native date type, so if we
    # leave them as-is, date filtering/sorting compares them as plain strings and
    # gives wrong results (e.g. '01-01-2011' sorts after '02-01-2011' is fine, but
    # '01-03-2014' vs '01-01-2011' compares incorrectly across years/months).
    # Converting to YYYY-MM-DD text makes string comparison == chronological comparison.
    df["order_date"] = pd.to_datetime(df["order_date"], format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
    df["ship_date"] = pd.to_datetime(df["ship_date"], format="%d-%m-%Y").dt.strftime("%Y-%m-%d")

    print(f"Loaded {len(df)} rows. Writing to {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("sales", conn, if_exists="replace", index=False)

    # quick verification
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sales")
    count = cur.fetchone()[0]
    conn.close()

    print(f"Done. sales.db now has a 'sales' table with {count} rows.")

if __name__ == "__main__":
    main()
