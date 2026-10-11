import pandas as pd
from database import get_connection


# =========================================================
# SETTINGS
# =========================================================

CSV_FILE = "mobile_data_plan_recommendation_dataset.csv"

# Only 100 subscribers will be imported
NUMBER_OF_SUBSCRIBERS = 100


# =========================================================
# START
# =========================================================

print("=" * 50)
print("MOBILE DATA PLAN DATABASE IMPORT")
print("=" * 50)


# =========================================================
# LOAD CSV
# =========================================================

print("\nLoading CSV file...")

try:
    df = pd.read_csv(CSV_FILE)

    print("CSV loaded successfully!")
    print("Original rows:", len(df))
    print("Columns:", len(df.columns))

except Exception as e:
    print("Error loading CSV:")
    print(e)
    exit()


# =========================================================
# KEEP ONLY 100 SUBSCRIBERS
# =========================================================

df = df.head(NUMBER_OF_SUBSCRIBERS)

print("\nUsing only first 100 subscribers.")
print("Rows to insert:", len(df))


# =========================================================
# CHECK DATA
# =========================================================

if len(df) == 0:
    print("No data found in CSV.")
    exit()

if len(df) < NUMBER_OF_SUBSCRIBERS:
    print(
        f"Warning: CSV contains only {len(df)} rows."
    )


# =========================================================
# CONNECT TO MYSQL
# =========================================================

print("\nConnecting to MySQL...")

try:
    connection = get_connection()
    cursor = connection.cursor()

    print("MySQL connected successfully!")

except Exception as e:
    print("MySQL connection failed:")
    print(e)
    exit()


# =========================================================
# CLEAR OLD SUBSCRIBER DATA
# =========================================================

print("\nClearing old subscriber records...")

try:
    cursor.execute(
        "SET FOREIGN_KEY_CHECKS = 0"
    )

    cursor.execute(
        "TRUNCATE TABLE subscribers"
    )

    cursor.execute(
        "SET FOREIGN_KEY_CHECKS = 1"
    )

    connection.commit()

    print("Old subscriber data cleared successfully!")

except Exception as e:
    print("Error clearing old data:")
    print(e)

    cursor.close()
    connection.close()
    exit()


# =========================================================
# INSERT QUERY
# =========================================================

insert_query = """
INSERT INTO subscribers (
    subscriber_id,
    age,
    region,
    tenure_months,
    current_plan,
    data_limit_gb,
    data_usage_gb,
    call_limit_min,
    call_minutes,
    sms_limit,
    sms_usage,
    last_month_data_gb,
    last_month_calls,
    last_month_sms,
    future_data_gb,
    future_call_minutes,
    future_sms,
    recommended_plan,
    data_overage_gb,
    call_overage_min,
    sms_overage,
    overage_flag,
    monthly_base_price,
    overage_charge,
    total_bill,
    payment_method,
    churn_risk
)
VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s
)
"""


# =========================================================
# INSERT 100 RECORDS
# =========================================================

print("\nInserting subscribers into MySQL...")

inserted = 0

try:

    for _, row in df.iterrows():

        values = (
            row["subscriber_id"],
            row["age"],
            row["region"],
            row["tenure_months"],
            row["current_plan"],
            row["data_limit_gb"],
            row["data_usage_gb"],
            row["call_limit_min"],
            row["call_minutes"],
            row["sms_limit"],
            row["sms_usage"],
            row["last_month_data_gb"],
            row["last_month_calls"],
            row["last_month_sms"],
            row["future_data_gb"],
            row["future_call_minutes"],
            row["future_sms"],
            row["recommended_plan"],
            row["data_overage_gb"],
            row["call_overage_min"],
            row["sms_overage"],
            row["overage_flag"],
            row["monthly_base_price"],
            row["overage_charge"],
            row["total_bill"],
            row["payment_method"],
            row["churn_risk"]
        )

        cursor.execute(
            insert_query,
            values
        )

        inserted += 1

    connection.commit()

    print("\nData inserted successfully!")
    print("Rows inserted:", inserted)

except Exception as e:

    connection.rollback()

    print("\nError inserting data:")
    print(e)

    cursor.close()
    connection.close()
    exit()


# =========================================================
# VERIFY DATABASE
# =========================================================

print("\nVerifying database...")

try:

    cursor.execute(
        "SELECT COUNT(*) FROM subscribers"
    )

    result = cursor.fetchone()

    total = result[0]

    print(
        "Total subscribers in MySQL:",
        total
    )

except Exception as e:

    print("Verification error:")
    print(e)


# =========================================================
# SHOW FIRST 10 SUBSCRIBERS
# =========================================================

print("\nFirst 10 subscribers:")

try:

    cursor.execute(
        """
        SELECT
            subscriber_id,
            region,
            current_plan,
            data_usage_gb,
            call_minutes,
            sms_usage,
            total_bill
        FROM subscribers
        ORDER BY subscriber_id
        LIMIT 10
        """
    )

    records = cursor.fetchall()

    for record in records:
        print(record)

except Exception as e:

    print("Error displaying subscribers:")
    print(e)


# =========================================================
# CLOSE CONNECTION
# =========================================================

cursor.close()
connection.close()

print("\n" + "=" * 50)
print("DATABASE IMPORT COMPLETED")
print("=" * 50)