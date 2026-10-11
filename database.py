import os
import mysql.connector


def get_connection():
    """
    Create a MySQL-compatible database connection using environment variables.

    Configure these variables in Render:
      DB_HOST
      DB_USER
      DB_PASSWORD
      DB_NAME
      DB_PORT (optional; defaults to 4000 for TiDB Cloud, otherwise 3306)

    For local development, set the same variables in your local environment.
    """
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME", "mobile_plan_db")
    port = int(os.getenv("DB_PORT", "3306"))

    if not password:
        raise RuntimeError(
            "DB_PASSWORD is not set. Configure DB_HOST, DB_USER, DB_PASSWORD, "
            "DB_NAME, and DB_PORT in your environment."
        )

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        connection_timeout=15,
    )


if __name__ == "__main__":
    try:
        connection = get_connection()
        if connection.is_connected():
            print("MySQL connection successful!")
            print("Database:", os.getenv("DB_NAME", "mobile_plan_db"))
        connection.close()
    except (mysql.connector.Error, RuntimeError, ValueError) as error:
        print("MySQL connection failed!")
        print("Error:", error)
