"""Load the CSVs in ../data/ into Postgres.

Ported (load logic only) from AI_Data_Agent-reference/feed_db.py. The reference
file had no LangChain wiring — it's pure psycopg2 CREATE TABLE + COPY — so the
port is near-verbatim with these changes:
  - env-driven config (DB_* vars) instead of bare os.environ['host'] etc.
  - CSV_DIR points at ../data relative to this file (the project data folder).
  - same DDL, same load_csv() COPY logic, same TRUNCATE+reload, same counts.
No LangGraph/LangChain orchestration is ported or referenced.
"""

import os
import sys

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "data_agent_db"),
    "user": os.environ.get("DB_USER", "ramesh"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

# data/ lives one level up from mcp-server/.
CSV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

create_tables_sql = """

CREATE SCHEMA IF NOT EXISTS public;

-- USERS
CREATE TABLE IF NOT EXISTS public.users (
    user_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    city VARCHAR(100),
    province VARCHAR(50),
    user_type VARCHAR(20) NOT NULL,
    signup_date DATE,
    is_active BOOLEAN
);

-- VEHICLES
CREATE TABLE IF NOT EXISTS public.vehicles (
    vehicle_id INTEGER PRIMARY KEY,
    driver_id INTEGER NOT NULL,
    make VARCHAR(50),
    model VARCHAR(50),
    year INTEGER,
    license_plate VARCHAR(20) UNIQUE,
    color VARCHAR(30),
    is_active BOOLEAN,
    CONSTRAINT fk_vehicle_driver FOREIGN KEY (driver_id) REFERENCES public.users(user_id)
);

-- RIDES
CREATE TABLE IF NOT EXISTS public.rides (
    ride_id INTEGER PRIMARY KEY,
    rider_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    requested_at TIMESTAMP,
    pickup_time TIMESTAMP,
    dropoff_time TIMESTAMP,
    pickup_latitude DECIMAL(9,6),
    pickup_longitude DECIMAL(9,6),
    dropoff_latitude DECIMAL(9,6),
    dropoff_longitude DECIMAL(9,6),
    distance_km DECIMAL(10,2),
    fare DECIMAL(10,2),
    surge_multiplier DECIMAL(4,2),
    status VARCHAR(30),
    cancellation_reason VARCHAR(100),
    CONSTRAINT fk_ride_rider FOREIGN KEY (rider_id) REFERENCES public.users(user_id),
    CONSTRAINT fk_ride_driver FOREIGN KEY (driver_id) REFERENCES public.users(user_id)
);

-- PAYMENTS
CREATE TABLE IF NOT EXISTS public.payments (
    payment_id INTEGER PRIMARY KEY,
    ride_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10,2),
    payment_method VARCHAR(50),
    payment_status VARCHAR(30),
    transaction_id VARCHAR(100) UNIQUE,
    payment_time TIMESTAMP,
    CONSTRAINT fk_payment_ride FOREIGN KEY (ride_id) REFERENCES public.rides(ride_id),
    CONSTRAINT fk_payment_user FOREIGN KEY (user_id) REFERENCES public.users(user_id)
);

-- RATINGS
CREATE TABLE IF NOT EXISTS public.ratings (
    rating_id INTEGER PRIMARY KEY,
    ride_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    rating INTEGER,
    comment TEXT,
    rated_at TIMESTAMP,
    CONSTRAINT fk_rating_ride FOREIGN KEY (ride_id) REFERENCES public.rides(ride_id),
    CONSTRAINT fk_rating_rider FOREIGN KEY (rider_id) REFERENCES public.users(user_id),
    CONSTRAINT fk_rating_driver FOREIGN KEY (driver_id) REFERENCES public.users(user_id),
    CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS idx_vehicles_driver_id ON public.vehicles(driver_id);
CREATE INDEX IF NOT EXISTS idx_rides_rider_id ON public.rides(rider_id);
CREATE INDEX IF NOT EXISTS idx_rides_driver_id ON public.rides(driver_id);
CREATE INDEX IF NOT EXISTS idx_rides_requested_at ON public.rides(requested_at);
CREATE INDEX IF NOT EXISTS idx_rides_status ON public.rides(status);
CREATE INDEX IF NOT EXISTS idx_payments_ride_id ON public.payments(ride_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON public.payments(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_ride_id ON public.ratings(ride_id);
CREATE INDEX IF NOT EXISTS idx_ratings_driver_id ON public.ratings(driver_id);
"""


def load_csv(cursor, table_name, csv_file, columns):
    file_path = os.path.join(CSV_DIR, csv_file)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    copy_sql = sql.SQL("""
        COPY {} ({})
        FROM STDIN
        WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',', NULL '')
    """).format(
        sql.Identifier("public", table_name),
        sql.SQL(", ").join(sql.Identifier(c) for c in columns),
    )

    with open(file_path, "r", encoding="utf-8") as f:
        cursor.copy_expert(copy_sql, f)

    print(f"Loaded {csv_file}")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cursor = conn.cursor()
    print("Connected to PostgreSQL")

    cursor.execute(create_tables_sql)
    print("Tables created successfully")

    cursor.execute(
        "TRUNCATE TABLE public.ratings, public.payments, public.rides, public.vehicles, public.users CASCADE;"
    )

    load_csv(cursor, "users", "users.csv",
             ["user_id","first_name","last_name","email","phone","city","province","user_type","signup_date","is_active"])
    load_csv(cursor, "vehicles", "vehicles.csv",
             ["vehicle_id","driver_id","make","model","year","license_plate","color","is_active"])
    load_csv(cursor, "rides", "rides.csv",
             ["ride_id","rider_id","driver_id","requested_at","pickup_time","dropoff_time",
              "pickup_latitude","pickup_longitude","dropoff_latitude","dropoff_longitude",
              "distance_km","fare","surge_multiplier","status","cancellation_reason"])
    load_csv(cursor, "payments", "payments.csv",
             ["payment_id","ride_id","user_id","amount","payment_method","payment_status","transaction_id","payment_time"])
    load_csv(cursor, "ratings", "ratings.csv",
             ["rating_id","ride_id","rider_id","driver_id","rating","comment","rated_at"])

    tables = ["users", "vehicles", "rides", "payments", "ratings"]
    print("\nRecord counts:")
    print("-" * 40)
    for table in tables:
        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier("public"), sql.Identifier(table)))
        count = cursor.fetchone()[0]
        print(f"{table:<15} {count:>10,}")

    conn.commit()
    print("\nData loaded successfully!\nTransaction committed.")

    cursor.close()
    conn.close()
    print("PostgreSQL connection closed.")


if __name__ == "__main__":
    sys.exit(main())
