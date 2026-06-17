import sys
import cv2
import sqlite3
import numpy as np
import mediapipe as mp
import pyttsx3
import math
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QStackedWidget, QMessageBox, QComboBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QFrame, QSizePolicy, QGraphicsDropShadowEffect)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QLocale
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtTextToSpeech import QTextToSpeech

DB_NAME = 'telemedycyna.db'

# ==========================================
# MODERN UI STYLESHEET (QSS)
# ==========================================
STYLE_SHEET = """
* {
    font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
}
QMainWindow {
    background-color: #F4F7F6;
}
QLabel {
    font-size: 15px;
    color: #2C3E50;
}
QLabel#app_title {
    font-size: 20px;
    font-weight: 800;
    color: #1A365D;
}
QLabel#header {
    font-size: 24px;
    font-weight: 700;
    color: #1A365D;
    margin-bottom: 10px;
}
QLabel#video_feed {
    background-color: #000000;
    color: #FFFFFF;
    border-radius: 12px;
}
QLabel#error_msg {
    color: #EF4444;
    font-size: 11px;
    font-weight: bold;
    margin-bottom: 0px; 
}
QLineEdit {
    padding: 12px;
    font-size: 14px;
    color: #000000;
    font-weight: 600;
    border: 1px solid #9CA3AF;
    border-radius: 8px;
    background-color: #FFFFFF;
}
QLineEdit:focus {
    border: 2px solid #2563EB;
    background-color: #F8FAFC;
    color: #000000;
}
QLineEdit::placeholder {
    color: #6B7280;
    font-weight: normal;
}
QPushButton {
    background-color: #2563EB;
    color: white;
    padding: 12px 20px;
    font-size: 15px;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #1D4ED8;
}
QPushButton:disabled {
    background-color: #9CA3AF;
    color: #F3F4F6;
}
QPushButton#danger {
    background-color: #EF4444;
    padding: 10px 15px;
}
QPushButton#danger:hover {
    background-color: #DC2626;
}
QPushButton#secondary {
    background-color: #64748B;
}
QPushButton#secondary:hover {
    background-color: #475569;
}
QComboBox {
    padding: 12px;
    font-size: 14px;
    color: #000000;
    font-weight: 500;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    background-color: #FFFFFF;
}
QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    font-size: 14px;
    color: #000000;
    gridline-color: #E2E8F0;
}
QHeaderView::section {
    background-color: #F1F5F9;
    padding: 10px;
    font-weight: bold;
    color: #1E293B;
    border: none;
    border-bottom: 2px solid #CBD5E1;
}
QFrame#card {
    background-color: #FFFFFF;
    border-radius: 16px;
}
QFrame#navbar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E2E8F0;
}
QMessageBox {
    background-color: #FFFFFF;
}
"""


# ==========================================
# 1. BAZA DANYCH (SQLite)
# ==========================================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS tests
                          (
                              id INTEGER PRIMARY KEY,
                              patient_email TEXT,
                              result_data TEXT,
                              doctor_decision TEXT
                          )''')


# ==========================================
# 2. WĄTKI POBOCZNE (Audio i Wideo)
# ==========================================
class CameraMediaPipeThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    test_result_signal = pyqtSignal(str)

    def __init__(self, camera_id=0, test_type='right_arm'):
        super().__init__()
        self.camera_id = camera_id
        self.test_type = test_type
        self._run_flag = True
        self.test_passed = False

    def run(self):
        cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return

        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils

        with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while self._run_flag:
                try:
                    ret, frame = cap.read()
                    if not ret or frame is None or frame.size == 0:
                        QThread.msleep(10)
                        continue

                    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(image_rgb)

                    if results.pose_landmarks:
                        mp_drawing.draw_landmarks(image_rgb, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                        if not self.test_passed:
                            landmarks = results.pose_landmarks.landmark
                            r_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                            r_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
                            l_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                            l_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]

                            r_visible = r_shoulder.visibility > 0.5 and r_wrist.visibility > 0.5
                            l_visible = l_shoulder.visibility > 0.5 and l_wrist.visibility > 0.5
                            passed = False

                            if self.test_type == 'right_arm' and r_visible:
                                if r_wrist.y < r_shoulder.y: passed = True
                            elif self.test_type == 'left_arm' and l_visible:
                                if l_wrist.y < l_shoulder.y: passed = True
                            elif self.test_type == 'both_arms' and r_visible and l_visible:
                                if r_wrist.y < r_shoulder.y and l_wrist.y < l_shoulder.y: passed = True
                            elif self.test_type == 'hands_together' and r_visible and l_visible:
                                dist = math.hypot(r_wrist.x - l_wrist.x, r_wrist.y - l_wrist.y)
                                if dist < 0.05: passed = True

                            if passed:
                                self.test_passed = True
                                self.test_result_signal.emit("Sukces: Zadanie wykonane poprawnie.")

                    final_frame = np.require(image_rgb, dtype=np.uint8, requirements=['C_CONTIGUOUS'])
                    h, w, ch = final_frame.shape
                    bytes_per_line = ch * w

                    q_img = QImage(final_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
                    self.change_pixmap_signal.emit(q_img)

                except Exception as e:
                    pass

                QThread.msleep(30)
        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()


# ==========================================
# 3. GŁÓWNE OKNA APLIKACJI (GUI)
# ==========================================
class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tts = QTextToSpeech()
        self.tts.setLocale(QLocale(QLocale.Language.Polish))
        self.setWindowTitle("System Diagnostyki Neurologicznej")
        self.setMinimumSize(1000, 750)
        self.setStyleSheet(STYLE_SHEET)

        self.current_user_email = None

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.init_login_screen()
        self.init_patient_screen()
        self.init_doctor_screen()
        self.init_register_screen()

        self.stacked_widget.setCurrentIndex(0)

    def create_shadow(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 8)
        return shadow

    def create_navbar(self):
        navbar = QFrame()
        navbar.setObjectName("navbar")
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(30, 15, 30, 15)

        app_logo_title = QLabel("Telemedycyna AI")
        app_logo_title.setObjectName("app_title")

        logout_btn = QPushButton("Wyloguj")
        logout_btn.setObjectName("danger")
        logout_btn.clicked.connect(self.logout)
        logout_btn.setFixedWidth(120)

        nav_layout.addWidget(app_logo_title)
        nav_layout.addStretch()
        nav_layout.addWidget(logout_btn)
        navbar.setLayout(nav_layout)
        return navbar

    def show_confirmation_dialog(self, title, text):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(f"<b>{title}</b>")
        msg.setInformativeText(text)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        button_yes = msg.button(QMessageBox.StandardButton.Yes)
        button_yes.setText("Tak")

        button_no = msg.button(QMessageBox.StandardButton.No)
        button_no.setText("Nie")

        return msg.exec() == QMessageBox.StandardButton.Yes

    # --- EKRAN LOGOWANIA ---
    def init_login_screen(self):
        widget = QWidget()
        main_layout = QVBoxLayout()

        login_container = QFrame()
        login_container.setObjectName("card")
        login_container.setFixedSize(450, 480)
        login_container.setGraphicsEffect(self.create_shadow())

        login_layout = QVBoxLayout()
        login_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        login_layout.setContentsMargins(40, 40, 40, 40)
        login_layout.setSpacing(15)

        header = QLabel("Witaj ponownie")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub_header = QLabel("Zaloguj się, aby kontynuować.")
        sub_header.setStyleSheet("color: #64748B; margin-bottom: 10px;")
        sub_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.login_error_label = QLabel()
        self.login_error_label.setObjectName("error_msg")
        self.login_error_label.setVisible(False)
        self.login_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Adres e-mail")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Hasło")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        login_btn = QPushButton("Zaloguj się")
        login_btn.clicked.connect(self.handle_login)

        register_btn = QPushButton("Zarejestruj się")
        register_btn.setObjectName("secondary")
        register_btn.clicked.connect(self.go_to_register)

        login_layout.addWidget(header)
        login_layout.addWidget(sub_header)
        login_layout.addWidget(self.login_error_label)
        login_layout.addWidget(self.email_input)
        login_layout.addWidget(self.pass_input)
        login_layout.addSpacing(10)
        login_layout.addWidget(login_btn)
        login_layout.addWidget(register_btn)

        login_container.setLayout(login_layout)
        main_layout.addWidget(login_container, alignment=Qt.AlignmentFlag.AlignCenter)
        widget.setLayout(main_layout)
        self.stacked_widget.addWidget(widget)

    # --- EKRAN REJESTRACJI ---
    def init_register_screen(self):
        widget = QWidget()
        main_layout = QVBoxLayout()

        register_container = QFrame()
        register_container.setObjectName("card")
        register_container.setFixedWidth(550)
        register_container.setGraphicsEffect(self.create_shadow())

        register_layout = QVBoxLayout()
        register_layout.setContentsMargins(40, 30, 40, 30)
        register_layout.setSpacing(10)

        header = QLabel("Nowe konto")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        register_layout.addWidget(header)
        register_layout.addSpacing(10)

        def create_error_label():
            lbl = QLabel()
            lbl.setObjectName("error_msg")
            lbl.setVisible(False)
            lbl.setWordWrap(True)
            return lbl

        # RZĄD 1: IMIĘ (Lewo) i NAZWISKO (Prawo)
        row1 = QHBoxLayout()
        row1.setSpacing(15)

        col1 = QVBoxLayout();
        col1.setSpacing(2)
        self.reg_first_name = QLineEdit()
        self.reg_first_name.setPlaceholderText("Imię")
        self.err_first_name = create_error_label()
        col1.addWidget(self.err_first_name)
        col1.addWidget(self.reg_first_name)

        col2 = QVBoxLayout();
        col2.setSpacing(2)
        self.reg_last_name = QLineEdit()
        self.reg_last_name.setPlaceholderText("Nazwisko")
        self.err_last_name = create_error_label()
        col2.addWidget(self.err_last_name)
        col2.addWidget(self.reg_last_name)

        row1.addLayout(col1)
        row1.addLayout(col2)
        register_layout.addLayout(row1)

        # RZĄD 2: EMAIL (Na całą szerokość)
        self.reg_email = QLineEdit()
        self.reg_email.setPlaceholderText("Adres e-mail")
        self.err_email = create_error_label()
        register_layout.addWidget(self.err_email)
        register_layout.addWidget(self.reg_email)

        # RZĄD 3: TELEFON (Lewo) i PESEL (Prawo)
        row2 = QHBoxLayout()
        row2.setSpacing(15)

        col3 = QVBoxLayout();
        col3.setSpacing(2)
        self.reg_phone = QLineEdit()
        self.reg_phone.setPlaceholderText("Numer telefonu")
        self.err_phone = create_error_label()
        col3.addWidget(self.err_phone)
        col3.addWidget(self.reg_phone)

        col4 = QVBoxLayout();
        col4.setSpacing(2)
        self.reg_pesel = QLineEdit()
        self.reg_pesel.setPlaceholderText("Numer PESEL")
        self.err_pesel = create_error_label()
        col4.addWidget(self.err_pesel)
        col4.addWidget(self.reg_pesel)

        row2.addLayout(col3)
        row2.addLayout(col4)
        register_layout.addLayout(row2)

        # RZĄD 4: HASŁO
        self.reg_pass = QLineEdit()
        self.reg_pass.setPlaceholderText("Hasło")
        self.reg_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.err_pass = create_error_label()
        register_layout.addWidget(self.err_pass)
        register_layout.addWidget(self.reg_pass)

        # RZĄD 5: WYBÓR ROLI I LICENCJA
        role_label = QLabel("Wybierz rolę:")
        role_label.setStyleSheet("margin-top: 5px;")
        register_layout.addWidget(role_label)

        self.reg_role_combo = QComboBox()
        self.reg_role_combo.addItem("Pacjent", "pacjent")
        self.reg_role_combo.addItem("Lekarz", "lekarz")
        self.reg_role_combo.currentIndexChanged.connect(self.toggle_license_field)
        register_layout.addWidget(self.reg_role_combo)

        self.reg_license = QLineEdit()
        self.reg_license.setPlaceholderText("Numer licencji (tylko lekarz)")
        self.reg_license.setVisible(False)
        self.err_license = create_error_label()
        register_layout.addWidget(self.err_license)
        register_layout.addWidget(self.reg_license)

        # RZĄD 6: PRZYCISKI
        register_layout.addSpacing(15)
        create_acc_btn = QPushButton("Utwórz konto")
        create_acc_btn.clicked.connect(self.handle_register)
        register_layout.addWidget(create_acc_btn)

        back_to_login_btn = QPushButton("Wróć do logowania")
        back_to_login_btn.setObjectName("secondary")
        back_to_login_btn.clicked.connect(self.go_to_login)
        register_layout.addWidget(back_to_login_btn)

        register_container.setLayout(register_layout)
        main_layout.addWidget(register_container, alignment=Qt.AlignmentFlag.AlignCenter)
        widget.setLayout(main_layout)
        self.stacked_widget.addWidget(widget)

    def toggle_license_field(self):
        if self.reg_role_combo.currentData() == "lekarz":
            self.reg_license.setVisible(True)
        else:
            self.reg_license.setVisible(False)
            self.err_license.setVisible(False)
            self.reg_license.clear()

    # --- EKRAN PACJENTA ---
    def init_patient_screen(self):
        self.patient_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.create_navbar())

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(40, 30, 40, 40)

        card = QFrame()
        card.setObjectName("card")
        card.setGraphicsEffect(self.create_shadow())
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        title = QLabel("Panel Pacjenta")
        title.setObjectName("header")
        self.info_label = QLabel("Oczekiwanie na wybór testu...")
        self.info_label.setStyleSheet("font-size: 16px; color: #64748B; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.info_label)

        self.video_label = QLabel("Kamera wyłączona")
        self.video_label.setObjectName("video_feed")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setMinimumSize(640, 360)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)

        self.test_selector = QComboBox()
        self.test_selector.addItems([
            "Uniesienie prawej ręki",
            "Uniesienie lewej ręki",
            "Uniesienie obu rąk",
            "Złączenie dłoni przed sobą"
        ])
        self.test_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.start_test_btn = QPushButton("Rozpocznij Test")
        self.start_test_btn.clicked.connect(self.start_patient_test)

        control_layout.addWidget(QLabel("Wybierz test:"))
        control_layout.addWidget(self.test_selector)
        control_layout.addWidget(self.start_test_btn)

        card_layout.addLayout(header_layout)
        card_layout.addWidget(self.video_label, stretch=1)
        card_layout.addLayout(control_layout)

        card.setLayout(card_layout)
        content_layout.addWidget(card)
        layout.addLayout(content_layout)

        self.patient_widget.setLayout(layout)
        self.stacked_widget.addWidget(self.patient_widget)

    # --- EKRAN LEKARZA ---
    def init_doctor_screen(self):
        self.doctor_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.create_navbar())

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(40, 30, 40, 40)

        card = QFrame()
        card.setObjectName("card")
        card.setGraphicsEffect(self.create_shadow())
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(20)

        title = QLabel("Baza Wyników")
        title.setObjectName("header")

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["ID Badania", "Pacjent (Imię i Nazwisko)", "Wynik AI", "Status"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        refresh_btn = QPushButton("Odśwież wyniki")
        refresh_btn.setFixedWidth(200)
        refresh_btn.clicked.connect(self.load_doctor_results)

        card_layout.addWidget(title)
        card_layout.addWidget(QLabel("Ostatnie wyniki testów wykonane przez pacjentów:"))
        card_layout.addWidget(self.results_table)
        card_layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

        card.setLayout(card_layout)
        content_layout.addWidget(card)
        layout.addLayout(content_layout)

        self.doctor_widget.setLayout(layout)
        self.stacked_widget.addWidget(self.doctor_widget)

    # --- LOGIKA APLIKACJI ---
    def go_to_register(self):
        self.login_error_label.setVisible(False)
        self.stacked_widget.setCurrentIndex(3)

    def go_to_login(self):
        self.stacked_widget.setCurrentIndex(0)

    def reset_register_errors(self):
        for err_lbl in [self.err_first_name, self.err_last_name, self.err_email,
                        self.err_phone, self.err_pesel, self.err_pass, self.err_license]:
            err_lbl.setVisible(False)
            err_lbl.setText("")

    def handle_register(self):
        self.reset_register_errors()

        first_name = self.reg_first_name.text().strip()
        last_name = self.reg_last_name.text().strip()
        email = self.reg_email.text().strip()
        phone = self.reg_phone.text().strip()
        pesel = self.reg_pesel.text().strip()
        password = self.reg_pass.text().strip()
        role = self.reg_role_combo.currentData()
        license_num = self.reg_license.text().strip()

        is_valid = True

        if not re.match(r"^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ\s\-]+$", first_name):
            self.err_first_name.setText("Imię musi zaczynać się z wielkiej litery (tylko litery, min. 2 znaki).")
            self.err_first_name.setVisible(True)
            is_valid = False

        # ZMIANA: Walidacja nazwiska (musi zaczynać się z dużej litery)
        if not re.match(r"^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ\s\-]+$", last_name):
            self.err_last_name.setText("Nazwisko musi zaczynać się z wielkiej litery (tylko litery, min. 2 znaki).")
            self.err_last_name.setVisible(True)
            is_valid = False

        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            self.err_email.setText("Podaj poprawny adres e-mail (np. kowalski@mail.com).")
            self.err_email.setVisible(True)
            is_valid = False

        if not phone.isdigit() or len(phone) != 9:
            self.err_phone.setText("Numer telefonu musi składać się z dokładnie 9 cyfr.")
            self.err_phone.setVisible(True)
            is_valid = False

        if not pesel.isdigit() or len(pesel) != 11:
            self.err_pesel.setText("Numer PESEL musi składać się z dokładnie 11 cyfr.")
            self.err_pesel.setVisible(True)
            is_valid = False

        if len(password) < 6:
            self.err_pass.setText("Hasło musi mieć co najmniej 6 znaków.")
            self.err_pass.setVisible(True)
            is_valid = False

        if role == "lekarz" and len(license_num) < 5:
            self.err_license.setText("Numer licencji medycznej musi mieć min. 5 znaków.")
            self.err_license.setVisible(True)
            is_valid = False

        if not is_valid:
            return

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email=?", (email,))
            if cursor.fetchone():
                self.err_email.setText("Konto z tym adresem e-mail już istnieje!")
                self.err_email.setVisible(True)
                return

            cursor.execute("""
                           INSERT INTO users (email, password, role, first_name, last_name, phone, pesel,
                                              license_number)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           """, (email, password, role, first_name, last_name, phone, pesel, license_num))
            conn.commit()

        QMessageBox.information(self, "Sukces", "Konto zostało pomyślnie utworzone!")

        for field in [self.reg_first_name, self.reg_last_name, self.reg_email, self.reg_phone, self.reg_pesel,
                      self.reg_pass, self.reg_license]:
            field.clear()

        self.go_to_login()

    def handle_login(self):
        self.login_error_label.setVisible(False)
        email = self.email_input.text().strip()
        password = self.pass_input.text().strip()

        if not email or not password:
            self.login_error_label.setText("Wprowadź adres e-mail oraz hasło.")
            self.login_error_label.setVisible(True)
            return

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM users WHERE email=? AND password=?", (email, password))
            result = cursor.fetchone()

        if result:
            role = result[0]
            self.current_user_email = email
            if role == 'pacjent':
                self.stacked_widget.setCurrentIndex(1)
            elif role == 'lekarz':
                self.load_doctor_results()
                self.stacked_widget.setCurrentIndex(2)
        else:
            self.login_error_label.setText("Nieprawidłowy adres e-mail lub hasło!")
            self.login_error_label.setVisible(True)

    def request_video_consent(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Wymagana Zgoda")
        msg.setText("<b>Ochrona Danych Osobowych</b>")
        msg.setInformativeText(
            "Czy zgadzasz się na to, aby Twoje dane wideo były przetwarzane w celach diagnostycznych?")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        button_yes = msg.button(QMessageBox.StandardButton.Yes)
        button_yes.setText("Wyrażam zgodę")
        button_no = msg.button(QMessageBox.StandardButton.No)
        button_no.setText("Odmów")
        return msg.exec() == QMessageBox.StandardButton.Yes

    def start_patient_test(self):
        if not self.request_video_consent():
            self.info_label.setText("Test anulowany: Brak zgody na wideo.")
            self.info_label.setStyleSheet("color: #EF4444; font-weight: bold;")
            return

        self.start_test_btn.setEnabled(False)
        self.test_selector.setEnabled(False)

        test_index = self.test_selector.currentIndex()
        if test_index == 0:
            test_type, instruction = 'right_arm', "Proszę podnieść prawą rękę do góry."
        elif test_index == 1:
            test_type, instruction = 'left_arm', "Proszę podnieść lewą rękę do góry."
        elif test_index == 2:
            test_type, instruction = 'both_arms', "Proszę podnieść obie ręce do góry."
        elif test_index == 3:
            test_type, instruction = 'hands_together', "Proszę wyciągnąć ręce i złączyć dłonie przed sobą."

        self.info_label.setText(f"Test w toku: {instruction}")
        self.info_label.setStyleSheet("color: #F59E0B; font-weight: bold;")
        self.tts.say(f"Rozpoczynamy badanie. {instruction}")

        self.camera_thread = CameraMediaPipeThread(test_type=test_type)
        self.camera_thread.change_pixmap_signal.connect(self.update_image)
        self.camera_thread.test_result_signal.connect(self.handle_test_success)
        self.camera_thread.start()

    def handle_test_success(self, message):
        self.info_label.setText(message)
        self.info_label.setStyleSheet("color: #10B981; font-weight: bold;")
        self.tts.say("Zadanie wykonane poprawnie. Dziękuję.")

        test_name = self.test_selector.currentText()
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tests (patient_email, result_data, doctor_decision) VALUES (?, ?, ?)",
                           (self.current_user_email, f"Zaliczony: {test_name}", "Do weryfikacji"))

    def update_image(self, q_img):
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def load_doctor_results(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT t.id, u.first_name || ' ' || u.last_name, t.result_data, t.doctor_decision
                           FROM tests t
                                    JOIN users u ON t.patient_email = u.email
                           """)
            rows = cursor.fetchall()

        self.results_table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.results_table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_table.setItem(row_idx, col_idx, item)

    # Zapytanie przed wylogowaniem
    def logout(self):
        if not self.show_confirmation_dialog("Wylogowanie", "Czy na pewno chcesz wylogować się z obecnego konta?"):
            return

        if hasattr(self, 'camera_thread') and self.camera_thread.isRunning():
            self.camera_thread.stop()

        if hasattr(self, 'start_test_btn'):
            self.start_test_btn.setEnabled(True)
            self.test_selector.setEnabled(True)
            self.info_label.setText("Oczekiwanie na wybór testu...")
            self.info_label.setStyleSheet("font-size: 16px; color: #64748B; font-weight: bold;")
            self.video_label.clear()
            self.video_label.setText("Kamera wyłączona")

        self.current_user_email = None
        self.email_input.clear()
        self.pass_input.clear()
        self.login_error_label.setVisible(False)
        self.stacked_widget.setCurrentIndex(0)

    # Zapytanie przed zamknięciem aplikacji
    def closeEvent(self, event):
        if self.show_confirmation_dialog("Zamykanie aplikacji", "Czy na pewno chcesz zamknąć program?"):
            if hasattr(self, 'camera_thread') and self.camera_thread.isRunning():
                self.camera_thread.stop()
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    try:
        import mediapipe as mp

        test_pose = mp.solutions.pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        test_pose.close()
    except Exception as e:
        pass

    init_db()
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())