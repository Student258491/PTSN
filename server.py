from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import uvicorn

app = FastAPI(title="Telemedycyna API")
DB_NAME = 'telemedycyna.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                          (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT,
                           role TEXT, first_name TEXT, last_name TEXT, phone TEXT,
                           pesel TEXT, license_number TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tests
                          (id INTEGER PRIMARY KEY, patient_email TEXT,
                           result_data TEXT, doctor_decision TEXT)''')
init_db()

class UserRegister(BaseModel):
    email: str; password: str; role: str; first_name: str; last_name: str; phone: str; pesel: str; license_number: str

class UserLogin(BaseModel):
    email: str; password: str

class TestResult(BaseModel):
    patient_email: str; result_data: str; doctor_decision: str

@app.post("/api/register")
def register(user: UserRegister):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email=?", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Konto już istnieje")
        cursor.execute("""
            INSERT INTO users (email, password, role, first_name, last_name, phone, pesel, license_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user.email, user.password, user.role, user.first_name, user.last_name, user.phone, user.pesel, user.license_number))
        conn.commit()
    return {"status": "success"}

@app.post("/api/login")
def login(user: UserLogin):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE email=? AND password=?", (user.email, user.password))
        result = cursor.fetchone()
        if result:
            return {"status": "success", "role": result[0]}
        raise HTTPException(status_code=401, detail="Błędne dane")

@app.post("/api/tests")
def add_test(test: TestResult):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tests (patient_email, result_data, doctor_decision) VALUES (?, ?, ?)",
                       (test.patient_email, test.result_data, test.doctor_decision))
        conn.commit()
    return {"status": "success"}

@app.get("/api/tests")
def get_tests():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, u.first_name || ' ' || u.last_name, t.result_data, t.doctor_decision
            FROM tests t JOIN users u ON t.patient_email = u.email
        """)
        rows = cursor.fetchall()
    return {"tests": rows}

@app.delete("/api/tests")
def clear_tests():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tests")
        conn.commit()
    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)