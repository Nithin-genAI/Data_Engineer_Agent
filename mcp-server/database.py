"""Postgres connection util — ported from AI_Data_Agent-reference/utils/database.py.

Only the connection pattern and the two operations we need (schema_details,
execute_sql) are kept. The module-level test harness at the bottom of the
original file is dropped. No safety/validation logic is added here — TrueForge's
approval gate is the safety layer.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _conn_details() -> dict:
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5432"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "dbname": os.environ.get("DB_NAME", "postgres"),
    }


class DatabaseUtil:
    def __init__(self, db_config: dict | None = None):
        self.db_config = db_config or _conn_details()
        self.connection = None
        try:
            self.connection = psycopg2.connect(**self.db_config)
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None

    def schema_details(self, schema_name: str = "public") -> str:
        """Fetch table names, column names/types and 5 sample rows for a schema.

        Ported verbatim in logic from the reference DatabaseUtil.schema_details.
        """
        schema_info_context = ""
        connection = self.connection
        cursor = connection.cursor()

        schema_info_context = f"Database Schema: {schema_name}\n"

        try:
            cursor.execute(
                "SELECT table_name from information_schema.tables where table_schema = %s;",
                (schema_name,),
            )
            tables_list = cursor.fetchall()

            for table in tables_list:
                table_name = table[0]
                schema_info_context = f"{schema_info_context}\nTable: {table_name}\n"

                cursor.execute(
                    "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;",
                    (table_name,),
                )
                columns_list = cursor.fetchall()
                for column in columns_list:
                    column_name, data_type = column[0], column[1]
                    schema_info_context = (
                        f"{schema_info_context}  Column: {column_name}, Data Type: {data_type}\n"
                    )

                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5;")
                sample_data = cursor.fetchall()
                schema_info_context = f"{schema_info_context}  Sample Data:\n"
                for row in sample_data:
                    schema_info_context = f"{schema_info_context}    {row}\n"

        except Exception as e:
            print(f"Error fetching schema details: {e}")
            schema_info_context = f"Error fetching schema details: {e}"

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        return schema_info_context

    def execute_sql(self, query: str) -> str:
        """Run a SQL query and return the rows as a string.

        No is_safe / keyword check is ported — that was the reference repo's
        safety layer, which TrueForge's approval gate replaces.
        """
        try:
            connection = self.connection
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            connection.commit()
            return str(result)
        except Exception as e:
            print(f"Error executing query: {e}")
            return f"Error executing query: {e}"
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
