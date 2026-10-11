import mysql.connector


def get_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Thouseef@32A2",
        database="mobile_plan_db"
    )

    return connection


if __name__ == "__main__":

    try:
        connection = get_connection()

        if connection.is_connected():
            print("MySQL connection successful!")
            print("Database: mobile_plan_db")

        connection.close()

    except mysql.connector.Error as error:

        print("MySQL connection failed!")
        print("Error:", error)