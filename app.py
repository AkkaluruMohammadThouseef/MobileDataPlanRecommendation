from flask import Flask, render_template, request, redirect, session

from database import get_connection

app = Flask(__name__)

app.secret_key = "mobile_data_plan_secret_key"


# Add columns expected by this application if the existing tables are older.
# This preserves existing rows and does not delete any data.
_schema_ready = False

def ensure_database_schema():
    global _schema_ready
    if _schema_ready:
        return

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW TABLES LIKE 'users'")
        if cursor.fetchone() is None:
            cursor.execute(
                "CREATE TABLE users ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "username VARCHAR(100) NOT NULL UNIQUE, "
                "password VARCHAR(255) NOT NULL, "
                "subscriber_id INT NULL)"
            )

        cursor.execute("SHOW COLUMNS FROM users LIKE 'subscriber_id'")
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE users ADD COLUMN subscriber_id INT NULL")

        cursor.execute("SHOW TABLES LIKE 'subscribers'")
        if cursor.fetchone() is None:
            cursor.execute(
                "CREATE TABLE subscribers ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "phone_number VARCHAR(20), plan_name VARCHAR(100), "
                "monthly_price DECIMAL(10,2), data_limit VARCHAR(50), "
                "validity_days INT)"
            )

        # These columns are read by dashboard, analytics, and usage pages.
        required_columns = {
            "subscriber_code": "VARCHAR(30) NULL UNIQUE",
            "age": "INT NULL",
            "region": "VARCHAR(50) NULL",
            "tenure_months": "INT NULL",
            "current_plan": "VARCHAR(100) NULL",
            "last_month_data_gb": "DECIMAL(10,2) DEFAULT 0",
            "last_month_calls": "DECIMAL(10,2) DEFAULT 0",
            "last_month_sms": "INT DEFAULT 0",
            "future_data_gb": "DECIMAL(10,2) DEFAULT 0",
            "future_call_minutes": "DECIMAL(10,2) DEFAULT 0",
            "future_sms": "INT DEFAULT 0",
            "recommended_plan": "VARCHAR(100) NULL",
            "data_overage_gb": "DECIMAL(10,2) DEFAULT 0",
            "call_overage_min": "DECIMAL(10,2) DEFAULT 0",
            "sms_overage": "INT DEFAULT 0",
            "monthly_base_price": "DECIMAL(10,2) DEFAULT 0",
            "overage_charge": "DECIMAL(10,2) DEFAULT 0",
            "payment_method": "VARCHAR(50) NULL",
            "churn_risk": "VARCHAR(30) NULL",
            "data_usage_gb": "DECIMAL(10,2) DEFAULT 0",
            "data_limit_gb": "DECIMAL(10,2) DEFAULT 0",
            "call_minutes": "DECIMAL(10,2) DEFAULT 0",
            "call_limit_min": "DECIMAL(10,2) DEFAULT 0",
            "sms_usage": "INT DEFAULT 0",
            "sms_limit": "INT DEFAULT 0",
            "total_bill": "DECIMAL(10,2) DEFAULT 0",
            "overage_flag": "VARCHAR(10) DEFAULT 'No'",
        }
        for column, definition in required_columns.items():
            cursor.execute(f"SHOW COLUMNS FROM subscribers LIKE '{column}'")
            if cursor.fetchone() is None:
                cursor.execute(
                    f"ALTER TABLE subscribers ADD COLUMN `{column}` {definition}"
                )
        connection.commit()
        _schema_ready = True
    finally:
        cursor.close()
        connection.close()


@app.before_request
def prepare_database():
    ensure_database_schema()

# =========================================================

# LOGIN CHECK

# =========================================================

def login_required():

    if "user_id" not in session:

        return False

    return True

# =========================================================

# GET SELECTED SUBSCRIBER

# =========================================================

def get_selected_subscriber_id():
    """Return a valid subscriber ID for Profile and Usage pages.

    A login may have an empty or outdated subscriber_id in the session.
    In that case, use the first available subscriber instead of showing
    "Subscriber not found" immediately.
    """
    subscriber_id = session.get("selected_subscriber_id") or session.get("subscriber_id")

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if subscriber_id is not None:
            cursor.execute(
                "SELECT id FROM subscribers WHERE id = %s OR subscriber_code = %s LIMIT 1",
                (subscriber_id, str(subscriber_id)),
            )
            row = cursor.fetchone()
            if row:
                session["selected_subscriber_id"] = row["id"]
                session["subscriber_id"] = row["id"]
                return row["id"]

        cursor.execute("SELECT id FROM subscribers ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if row:
            subscriber_id = row["id"]
            session["selected_subscriber_id"] = subscriber_id
            session["subscriber_id"] = subscriber_id
            return subscriber_id

        session.pop("selected_subscriber_id", None)
        session.pop("subscriber_id", None)
        return None
    finally:
        cursor.close()
        connection.close()

# =========================================================

# GET ONE SUBSCRIBER

# =========================================================

def get_subscriber(subscriber_id):

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    query = """

    SELECT subscribers.*, subscribers.subscriber_code AS subscriber_id

    FROM subscribers

    WHERE id = %s OR subscriber_code = %s

    LIMIT 1

    """

    cursor.execute(query, (subscriber_id, str(subscriber_id)))

    subscriber = cursor.fetchone()

    cursor.close()

    connection.close()

    return subscriber

# =========================================================

# LOGIN

# =========================================================

@app.route("/", methods=["GET", "POST"])

def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        query = """

        SELECT *

        FROM users

        WHERE username = %s

        AND password = %s

        """

        cursor.execute(query, (username, password))

        user = cursor.fetchone()

        cursor.close()

        connection.close()

        if user:

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            subscriber_id = user.get("subscriber_id")

            # If this login is not linked yet, use the first subscriber record.
            if subscriber_id is None:
                link_connection = get_connection()
                link_cursor = link_connection.cursor(dictionary=True)
                link_cursor.execute("SELECT id FROM subscribers ORDER BY id LIMIT 1")
                first_subscriber = link_cursor.fetchone()
                if first_subscriber:
                    subscriber_id = first_subscriber["id"]
                    link_cursor.execute(
                        "UPDATE users SET subscriber_id = %s WHERE id = %s",
                        (subscriber_id, user["id"]),
                    )
                    link_connection.commit()
                link_cursor.close()
                link_connection.close()

            session["subscriber_id"] = subscriber_id
            session["selected_subscriber_id"] = subscriber_id

            return redirect("/dashboard")

        else:

            return render_template(

                "login.html",

                error="Invalid username or password"

            )

    return render_template("login.html")

# =========================================================

# DASHBOARD

# =========================================================

@app.route("/dashboard")

def dashboard():

    if not login_required():

        return redirect("/")

    connection = get_connection()

    cursor = connection.cursor(dictionary=True)

    query = """

    SELECT subscribers.*, subscribers.subscriber_code AS subscriber_id

    FROM subscribers

    ORDER BY id

    """

    cursor.execute(query)

    all_subscribers = cursor.fetchall()

    # -----------------------------------------------------

    # TOTAL SUBSCRIBERS

    # -----------------------------------------------------

    total_subscribers = len(all_subscribers)

    # -----------------------------------------------------

    # SHOW ONLY 5 SUBSCRIBERS ON DASHBOARD

    # -----------------------------------------------------

    subscribers = all_subscribers[:5]

    # -----------------------------------------------------

    # INITIAL VALUES

    # -----------------------------------------------------

    overage_count = 0

    total_bill = 0

    total_data_usage = 0

    total_data_limit = 0

    total_call_usage = 0

    total_call_limit = 0

    total_sms_usage = 0

    total_sms_limit = 0

    # -----------------------------------------------------

    # CALCULATE BUSINESS METRICS

    # -----------------------------------------------------

    for subscriber in all_subscribers:

        # Overage count

        if str(subscriber["overage_flag"]) == "Yes":

            overage_count += 1

        # Total bill

        total_bill += float(

            subscriber["total_bill"] or 0

        )

        # Data

        total_data_usage += float(

            subscriber["data_usage_gb"] or 0

        )

        total_data_limit += float(

            subscriber["data_limit_gb"] or 0

        )

        # Calls

        total_call_usage += float(

            subscriber["call_minutes"] or 0

        )

        total_call_limit += float(

            subscriber["call_limit_min"] or 0

        )

        # SMS

        total_sms_usage += float(

            subscriber["sms_usage"] or 0

        )

        total_sms_limit += float(

            subscriber["sms_limit"] or 0

        )

    # -----------------------------------------------------

    # AVERAGE DATA USAGE

    # -----------------------------------------------------

    if total_subscribers > 0:

        average_data_usage = (

            total_data_usage / total_subscribers

        )

    else:

        average_data_usage = 0

    # -----------------------------------------------------

    # DATA PERCENTAGE

    # -----------------------------------------------------

    if total_data_limit > 0:

        data_percentage = (

            total_data_usage /

            total_data_limit

        ) * 100

    else:

        data_percentage = 0

    # -----------------------------------------------------

    # CALL PERCENTAGE

    # -----------------------------------------------------

    if total_call_limit > 0:

        call_percentage = (

            total_call_usage /

            total_call_limit

        ) * 100

    else:

        call_percentage = 0

    # -----------------------------------------------------

    # SMS PERCENTAGE

    # -----------------------------------------------------

    if total_sms_limit > 0:

        sms_percentage = (

            total_sms_usage /

            total_sms_limit

        ) * 100

    else:

        sms_percentage = 0

    # -----------------------------------------------------

    # PROGRESS BAR WIDTH

    # -----------------------------------------------------

    data_progress_width = min(

        data_percentage,

        100

    )

    call_progress_width = min(

        call_percentage,

        100

    )

    sms_progress_width = min(

        sms_percentage,

        100

    )

    cursor.close()

    connection.close()

    # -----------------------------------------------------

    # SEND DATA TO DASHBOARD

    # -----------------------------------------------------

    return render_template(

        "dashboard.html",

        subscribers=subscribers,

        total_subscribers=total_subscribers,

        overage_count=overage_count,

        total_bill=round(

            total_bill,

            2

        ),

        average_data_usage=round(

            average_data_usage,

            2

        ),

        data_percentage=round(

            data_percentage,

            1

        ),

        call_percentage=round(

            call_percentage,

            1

        ),

        sms_percentage=round(

            sms_percentage,

            1

        ),

        data_progress_width=round(

            data_progress_width,

            1

        ),

        call_progress_width=round(

            call_progress_width,

            1

        ),

        sms_progress_width=round(

            sms_progress_width,

            1

        )

    )

# =========================================================

# SUBSCRIBER MANAGEMENT

# =========================================================

@app.route("/subscribers")

def subscribers():

    if not login_required():

        return redirect("/")

    search = request.args.get(

        "search",

        ""

    ).strip()

    connection = get_connection()

    cursor = connection.cursor(

        dictionary=True

    )

    # -----------------------------------------------------

    # SEARCH ALL 100 SUBSCRIBERS

    # -----------------------------------------------------

    if search:

        query = """

        SELECT subscribers.*, subscribers.subscriber_code AS subscriber_id

        FROM subscribers

        WHERE subscriber_code LIKE %s
           OR phone_number LIKE %s
           OR CAST(id AS CHAR) LIKE %s

        ORDER BY id

        """

        cursor.execute(
            query,
            (f"%{search}%", f"%{search}%", f"%{search}%")
        )

    else:

        query = """

        SELECT subscribers.*, subscribers.subscriber_code AS subscriber_id

        FROM subscribers

        ORDER BY id

        """

        cursor.execute(query)

    subscribers = cursor.fetchall()

    cursor.close()

    connection.close()

    return render_template(

        "subscribers.html",

        subscribers=subscribers,

        search=search

    )

# =========================================================

# SEARCH SUBSCRIBER

# =========================================================

@app.route("/search-subscriber")

def search_subscriber():

    if not login_required():

        return redirect("/")

    subscriber_id = request.args.get(

        "subscriber_id",

        ""

    ).strip()

    # -----------------------------------------------------

    # EMPTY SEARCH

    # -----------------------------------------------------

    if subscriber_id == "":

        return redirect("/subscribers")

    # -----------------------------------------------------

    # SEARCH IN MYSQL

    # -----------------------------------------------------

    subscriber = get_subscriber(

        subscriber_id

    )

    # -----------------------------------------------------

    # NOT FOUND

    # -----------------------------------------------------

    if subscriber is None:

        return render_template(

            "subscribers.html",

            subscribers=[],

            search=subscriber_id,

            error="Subscriber ID not found"

        )

    # -----------------------------------------------------

    # STORE SELECTED SUBSCRIBER IN SESSION

    # -----------------------------------------------------

    session[

        "selected_subscriber_id"

    ] = subscriber_id

    # -----------------------------------------------------

    # OPEN PROFILE

    # -----------------------------------------------------

    return redirect(

        "/profile/" + subscriber_id

    )

# =========================================================

# PROFILE - SELECTED SUBSCRIBER

# =========================================================

@app.route("/profile")

def profile():

    if not login_required():

        return redirect("/")

    subscriber_id = get_selected_subscriber_id()

    subscriber = get_subscriber(

        subscriber_id

    )

    if subscriber is None:

        return "No subscriber records found. Import subscriber data first, then reopen Profile.", 404

    return render_template(

        "profile.html",

        subscriber=subscriber

    )

# =========================================================

# PROFILE - SPECIFIC SUBSCRIBER

# =========================================================

@app.route("/profile/<subscriber_id>")

def subscriber_profile(

    subscriber_id

):

    if not login_required():

        return redirect("/")

    subscriber_id = subscriber_id.strip()

    subscriber = get_subscriber(

        subscriber_id

    )

    if subscriber is None:

        return "Subscriber not found", 404

    # Store selected subscriber

    session[

        "selected_subscriber_id"

    ] = subscriber_id

    return render_template(

        "profile.html",

        subscriber=subscriber

    )

# =========================================================

# CALCULATE USAGE PERCENTAGES

# =========================================================

def calculate_usage_percentages(

    subscriber

):

    # -----------------------------------------------------

    # DATA

    # -----------------------------------------------------

    data_limit = float(

        subscriber["data_limit_gb"] or 0

    )

    data_usage = float(

        subscriber["data_usage_gb"] or 0

    )

    if data_limit > 0:

        data_percentage = (

            data_usage /

            data_limit

        ) * 100

    else:

        data_percentage = 0

    # -----------------------------------------------------

    # CALL

    # -----------------------------------------------------

    call_limit = float(

        subscriber["call_limit_min"] or 0

    )

    call_usage = float(

        subscriber["call_minutes"] or 0

    )

    if call_limit > 0:

        call_percentage = (

            call_usage /

            call_limit

        ) * 100

    else:

        call_percentage = 0

    # -----------------------------------------------------

    # SMS

    # -----------------------------------------------------

    sms_limit = float(

        subscriber["sms_limit"] or 0

    )

    sms_usage = float(

        subscriber["sms_usage"] or 0

    )

    if sms_limit > 0:

        sms_percentage = (

            sms_usage /

            sms_limit

        ) * 100

    else:

        sms_percentage = 0

    # -----------------------------------------------------

    # PROGRESS BAR WIDTH

    # -----------------------------------------------------

    data_progress_width = min(

        data_percentage,

        100

    )

    call_progress_width = min(

        call_percentage,

        100

    )

    sms_progress_width = min(

        sms_percentage,

        100

    )

    return {

        "data_percentage": round(

            data_percentage,

            1

        ),

        "call_percentage": round(

            call_percentage,

            1

        ),

        "sms_percentage": round(

            sms_percentage,

            1

        ),

        "data_progress_width": round(

            data_progress_width,

            1

        ),

        "call_progress_width": round(

            call_progress_width,

            1

        ),

        "sms_progress_width": round(

            sms_progress_width,

            1

        )

    }

# =========================================================

# USAGE PAGE

# =========================================================

@app.route("/usage")

def usage():

    if not login_required():

        return redirect("/")

    subscriber_id = get_selected_subscriber_id()

    subscriber = get_subscriber(

        subscriber_id

    )

    if subscriber is None:

        return "No subscriber records found. Import subscriber data first, then reopen Usage.", 404

    usage_data = calculate_usage_percentages(

        subscriber

    )

    return render_template(

        "usage.html",

        subscriber=subscriber,

        data_percentage=usage_data[

            "data_percentage"

        ],

        call_percentage=usage_data[

            "call_percentage"

        ],

        sms_percentage=usage_data[

            "sms_percentage"

        ],

        data_progress_width=usage_data[

            "data_progress_width"

        ],

        call_progress_width=usage_data[

            "call_progress_width"

        ],

        sms_progress_width=usage_data[

            "sms_progress_width"

        ]

    )

# =========================================================

# USAGE - SPECIFIC SUBSCRIBER

# =========================================================

@app.route("/usage/<subscriber_id>")

def subscriber_usage(

    subscriber_id

):

    if not login_required():

        return redirect("/")

    subscriber_id = subscriber_id.strip()

    subscriber = get_subscriber(

        subscriber_id

    )

    if subscriber is None:

        return "Subscriber not found", 404

    # Store selected subscriber

    session[

        "selected_subscriber_id"

    ] = subscriber_id

    usage_data = calculate_usage_percentages(

        subscriber

    )

    return render_template(

        "usage.html",

        subscriber=subscriber,

        data_percentage=usage_data[

            "data_percentage"

        ],

        call_percentage=usage_data[

            "call_percentage"

        ],

        sms_percentage=usage_data[

            "sms_percentage"

        ],

        data_progress_width=usage_data[

            "data_progress_width"

        ],

        call_progress_width=usage_data[

            "call_progress_width"

        ],

        sms_progress_width=usage_data[

            "sms_progress_width"

        ]

    )

# =========================================================

# ANALYTICS PAGE

# =========================================================

@app.route("/analytics")

def analytics():

    if not login_required():

        return redirect("/")

    connection = get_connection()

    cursor = connection.cursor(

        dictionary=True

    )

    query = """

    SELECT subscribers.*, subscribers.subscriber_code AS subscriber_id

    FROM subscribers

    ORDER BY id

    """

    cursor.execute(query)

    all_subscribers = cursor.fetchall()

    # -----------------------------------------------------

    # INITIAL VALUES

    # -----------------------------------------------------

    total_subscribers = len(

        all_subscribers

    )

    overage_count = 0

    total_bill = 0

    total_data_usage = 0

    total_data_limit = 0

    total_call_usage = 0

    total_call_limit = 0

    total_sms_usage = 0

    total_sms_limit = 0

    # -----------------------------------------------------

    # CALCULATE ANALYTICS

    # -----------------------------------------------------

    for subscriber in all_subscribers:

        # Overage

        if str(

            subscriber["overage_flag"]

        ) == "Yes":

            overage_count += 1

        # Bill

        total_bill += float(

            subscriber["total_bill"] or 0

        )

        # Data

        total_data_usage += float(

            subscriber["data_usage_gb"] or 0

        )

        total_data_limit += float(

            subscriber["data_limit_gb"] or 0

        )

        # Calls

        total_call_usage += float(

            subscriber["call_minutes"] or 0

        )

        total_call_limit += float(

            subscriber["call_limit_min"] or 0

        )

        # SMS

        total_sms_usage += float(

            subscriber["sms_usage"] or 0

        )

        total_sms_limit += float(

            subscriber["sms_limit"] or 0

        )

    # -----------------------------------------------------

    # AVERAGE DATA USAGE

    # -----------------------------------------------------

    if total_subscribers > 0:

        average_data_usage = (

            total_data_usage /

            total_subscribers

        )

    else:

        average_data_usage = 0

    # -----------------------------------------------------

    # DATA PERCENTAGE

    # -----------------------------------------------------

    if total_data_limit > 0:

        data_percentage = (

            total_data_usage /

            total_data_limit

        ) * 100

    else:

        data_percentage = 0

    # -----------------------------------------------------

    # CALL PERCENTAGE

    # -----------------------------------------------------

    if total_call_limit > 0:

        call_percentage = (

            total_call_usage /

            total_call_limit

        ) * 100

    else:

        call_percentage = 0

    # -----------------------------------------------------

    # SMS PERCENTAGE

    # -----------------------------------------------------

    if total_sms_limit > 0:

        sms_percentage = (

            total_sms_usage /

            total_sms_limit

        ) * 100

    else:

        sms_percentage = 0

    # -----------------------------------------------------

    # PROGRESS BAR WIDTH

    # -----------------------------------------------------

    data_progress_width = min(

        data_percentage,

        100

    )

    call_progress_width = min(

        call_percentage,

        100

    )

    sms_progress_width = min(

        sms_percentage,

        100

    )

    cursor.close()

    connection.close()

    # -----------------------------------------------------

    # SEND DATA TO ANALYTICS PAGE

    # -----------------------------------------------------

    return render_template(

        "analytics.html",

        total_subscribers=total_subscribers,

        overage_count=overage_count,

        total_bill=round(

            total_bill,

            2

        ),

        average_data_usage=round(

            average_data_usage,

            2

        ),

        data_percentage=round(

            data_percentage,

            1

        ),

        call_percentage=round(

            call_percentage,

            1

        ),

        sms_percentage=round(

            sms_percentage,

            1

        ),

        data_progress_width=round(

            data_progress_width,

            1

        ),

        call_progress_width=round(

            call_progress_width,

            1

        ),

        sms_progress_width=round(

            sms_progress_width,

            1

        )

    )

# =========================================================

# LOGOUT

# =========================================================

@app.route("/logout")

def logout():

    session.clear()

    return redirect("/")

# =========================================================

# RUN FLASK APPLICATION

# =========================================================

if __name__ == "__main__":

    app.run(

        debug=True

    )
