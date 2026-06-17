import sqlite3

DB_NAME = 'telemedycyna.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Initialize comprehensive user schema
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                          (
                              id INTEGER PRIMARY KEY,
                              email TEXT UNIQUE,
                              password TEXT,
                              role TEXT,
                              first_name TEXT,
                              last_name TEXT,
                              phone TEXT,
                              pesel TEXT,
                              license_number TEXT
                          )''')
        # Initialize test results schema
        cursor.execute('''CREATE TABLE IF NOT EXISTS tests
                          (
                              id INTEGER PRIMARY KEY,
                              patient_email TEXT,
                              result_data TEXT,
                              doctor_decision TEXT
                          )''')