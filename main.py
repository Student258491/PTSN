import sys
import cv2
import sqlite3
import numpy as np
import mediapipe as mp
import pyttsx3
import math
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

QLineEdit {
    padding: 14px;
    font-size: 15px;
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
    padding: 14px 20px;
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
QComboBox {
    padding: 12px;
    font-size: 15px;
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
                              id
                              INTEGER
                              PRIMARY
                              KEY,
                              username
                              TEXT,
                              password
                              TEXT,
                              role
                              TEXT
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tests
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY,
                              patient_username
                              TEXT,
                              result_data
                              TEXT,
                              doctor_decision
                              TEXT
                          )''')

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           ('pacjent1', '123', 'pacjent'))
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           ('lekarz1', '123', 'lekarz'))


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
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print(f"Błąd: Nie można otworzyć kamery o ID {self.camera_id}.")
            return

        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils

        with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while self._run_flag:
                ret, frame = cap.read()
                if ret:
                    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image_rgb.flags.writeable = False
                    results = pose.process(image_rgb)
                    image_rgb.flags.writeable = True

                    if results.pose_landmarks:
                        mp_drawing.draw_landmarks(
                            image_rgb, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                        # --- DIAGNOSTIC LOGIC ---
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

                    image_rgb = np.ascontiguousarray(image_rgb)
                    h, w, ch = image_rgb.shape
                    bytes_per_line = ch * w

                    q_img = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
                    self.change_pixmap_signal.emit(q_img)

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

        self.current_user = None

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.init_login_screen()
        self.init_patient_screen()
        self.init_doctor_screen()

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

    def init_login_screen(self):
        widget = QWidget()
        main_layout = QVBoxLayout()

        login_container = QFrame()
        login_container.setObjectName("card")
        login_container.setFixedSize(450, 400)
        login_container.setGraphicsEffect(self.create_shadow())

        login_layout = QVBoxLayout()
        login_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        login_layout.setContentsMargins(40, 40, 40, 40)
        login_layout.setSpacing(20)

        header = QLabel("Witaj ponownie")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub_header = QLabel("Zaloguj się, aby kontynuować.")
        sub_header.setStyleSheet("color: #64748B; margin-bottom: 10px;")
        sub_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Nazwa użytkownika")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Hasło")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        login_btn = QPushButton("Zaloguj się")
        login_btn.clicked.connect(self.handle_login)

        login_layout.addWidget(header)
        login_layout.addWidget(sub_header)
        login_layout.addWidget(self.user_input)
        login_layout.addWidget(self.pass_input)
        login_layout.addSpacing(10)
        login_layout.addWidget(login_btn)

        login_container.setLayout(login_layout)
        main_layout.addWidget(login_container, alignment=Qt.AlignmentFlag.AlignCenter)
        widget.setLayout(main_layout)
        self.stacked_widget.addWidget(widget)

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
            "Złączenie dłoni przed sobą (Palec-do-palca)"
        ])
        self.test_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.start_test_btn = QPushButton("Rozpocznij Test")
        self.start_test_btn.clicked.connect(self.start_patient_test)

        # Added Stop/Finish Button
        self.stop_test_btn = QPushButton("Zakończ Test")
        self.stop_test_btn.setObjectName("danger")
        self.stop_test_btn.setEnabled(False)
        self.stop_test_btn.clicked.connect(self.stop_patient_test)

        control_layout.addWidget(QLabel("Wybierz test:"))
        control_layout.addWidget(self.test_selector)
        control_layout.addWidget(self.start_test_btn)
        control_layout.addWidget(self.stop_test_btn)

        card_layout.addLayout(header_layout)
        card_layout.addWidget(self.video_label, stretch=1)
        card_layout.addLayout(control_layout)

        card.setLayout(card_layout)
        content_layout.addWidget(card)
        layout.addLayout(content_layout)

        self.patient_widget.setLayout(layout)
        self.stacked_widget.addWidget(self.patient_widget)

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
        self.results_table.setHorizontalHeaderLabels(["ID", "Pacjent", "Wynik AI", "Status"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Button configurations
        refresh_btn = QPushButton("Odśwież wyniki")
        refresh_btn.setFixedWidth(160)
        refresh_btn.clicked.connect(self.load_doctor_results)

        clear_db_btn = QPushButton("Wyczyść bazę")
        clear_db_btn.setObjectName("danger")  # Utilizes your existing red button styling
        clear_db_btn.setFixedWidth(160)
        clear_db_btn.clicked.connect(self.clear_database)

        # Horizontal layout to align buttons neatly to the right
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(clear_db_btn)

        card_layout.addWidget(title)
        card_layout.addWidget(QLabel("Ostatnie wyniki testów wykonane przez pacjentów:"))
        card_layout.addWidget(self.results_table)
        card_layout.addLayout(btn_layout)

        card.setLayout(card_layout)
        content_layout.addWidget(card)
        layout.addLayout(content_layout)

        self.doctor_widget.setLayout(layout)
        self.stacked_widget.addWidget(self.doctor_widget)

    def handle_login(self):
        username = self.user_input.text()
        password = self.pass_input.text()

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
            result = cursor.fetchone()

        if result:
            role = result[0]
            self.current_user = username
            if role == 'pacjent':
                self.stacked_widget.setCurrentIndex(1)
            elif role == 'lekarz':
                self.load_doctor_results()
                self.stacked_widget.setCurrentIndex(2)
        else:
            QMessageBox.warning(self, "Błąd", "Nieprawidłowe dane logowania!")

    def request_video_consent(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Wymagana Zgoda")
        msg.setText("<b>Ochrona Danych Osobowych</b>")
        msg.setInformativeText(
            "Czy zgadzasz się na to, aby Twoje dane wideo były przetwarzane i wykorzystywane przez personel medyczny w celach diagnostycznych?\n\n(I agree for my video data to be used by medics)")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        button_yes = msg.button(QMessageBox.StandardButton.Yes)
        button_yes.setText("Wyrażam zgodę")

        button_no = msg.button(QMessageBox.StandardButton.No)
        button_no.setText("Odmów")

        return msg.exec() == QMessageBox.StandardButton.Yes

    def start_patient_test(self):
        has_consent = self.request_video_consent()

        if not has_consent:
            self.info_label.setText("Test anulowany: Brak zgody na wideo.")
            self.info_label.setStyleSheet("color: #EF4444; font-weight: bold;")
            return

        self.start_test_btn.setEnabled(False)
        self.test_selector.setEnabled(False)
        self.stop_test_btn.setEnabled(True)

        test_index = self.test_selector.currentIndex()
        if test_index == 0:
            test_type = 'right_arm'
            instruction = "Proszę podnieść prawą rękę do góry."
        elif test_index == 1:
            test_type = 'left_arm'
            instruction = "Proszę podnieść lewą rękę do góry."
        elif test_index == 2:
            test_type = 'both_arms'
            instruction = "Proszę podnieść obie ręce do góry."
        elif test_index == 3:
            test_type = 'hands_together'
            instruction = "Proszę wyciągnąć ręce i złączyć dłonie przed sobą."

        self.info_label.setText(f"Test w toku: {instruction}")
        self.info_label.setStyleSheet("color: #F59E0B; font-weight: bold;")

        self.tts.say(f"Rozpoczynamy badanie. {instruction}")

        self.camera_thread = CameraMediaPipeThread(test_type=test_type)
        self.camera_thread.change_pixmap_signal.connect(self.update_image)
        self.camera_thread.test_result_signal.connect(self.handle_test_success)
        self.camera_thread.start()

    def stop_patient_test(self):
        """Halts the thread and records an unsuccessful attempt if the test wasn't passed."""
        if hasattr(self, 'camera_thread') and self.camera_thread.isRunning():
            passed = self.camera_thread.test_passed
            self.camera_thread.stop()

            test_name = self.test_selector.currentText()

            # Record failure if explicitly aborted before success criteria were met
            if not passed:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO tests (patient_username, result_data, doctor_decision) VALUES (?, ?, ?)",
                        (self.current_user, f"Nieudany (Przerwany): {test_name}", "Wymaga uwagi"))

                self.info_label.setText("Test przerwany przez pacjenta. Wynik: Nieudany.")
                self.info_label.setStyleSheet("color: #EF4444; font-weight: bold;")
                self.tts.say("Badanie zostało przerwane.")

        self.reset_patient_ui()

    def handle_test_success(self, message):
        self.info_label.setText(message)
        self.info_label.setStyleSheet("color: #10B981; font-weight: bold;")
        self.tts.say("Zadanie wykonane poprawnie. Dziękuję.")

        test_name = self.test_selector.currentText()
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tests (patient_username, result_data, doctor_decision) VALUES (?, ?, ?)",
                           (self.current_user, f"Zaliczony: {test_name}", "Do weryfikacji"))

    def update_image(self, q_img):
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def load_doctor_results(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, patient_username, result_data, doctor_decision FROM tests")
            rows = cursor.fetchall()

        self.results_table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.results_table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results_table.setItem(row_idx, col_idx, item)

    def reset_patient_ui(self):
        """Restores the initial UI state for the patient view."""
        self.start_test_btn.setEnabled(True)
        self.stop_test_btn.setEnabled(False)
        self.test_selector.setEnabled(True)
        self.video_label.clear()
        self.video_label.setText("Kamera wyłączona")

    def logout(self):
        # Gracefully handle abrupt logouts mid-test
        if hasattr(self, 'camera_thread') and self.camera_thread.isRunning():
            self.stop_patient_test()

        self.current_user = None
        self.user_input.clear()
        self.pass_input.clear()
        self.stacked_widget.setCurrentIndex(0)

        if hasattr(self, 'info_label'):
            self.info_label.setText("Oczekiwanie na wybór testu...")
            self.info_label.setStyleSheet("font-size: 16px; color: #64748B; font-weight: bold;")

    def closeEvent(self, event):
        if hasattr(self, 'camera_thread') and self.camera_thread.isRunning():
            self.camera_thread.stop()
        event.accept()

    def clear_database(self):
        """
        Inicjuje okno dialogowe i usuwa wszystkie rekordy z tabeli 'tests',
        resetując historię diagnostyczną pacjentów.
        """
        confirmation = QMessageBox.question(
            self,
            'Potwierdzenie operacji',
            'Czy na pewno chcesz usunąć wszystkie wyniki pacjentów z bazy danych?\nTej operacji nie można cofnąć.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirmation == QMessageBox.StandardButton.Yes:
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()

                    # Definitywne usunięcie wszystkich rekordów testowych
                    cursor.execute("DELETE FROM tests")

                    # Transakcja zostaje zatwierdzona.
                    # Brak ingerencji w 'sqlite_sequence', ponieważ mechanizm
                    # ROWID samodzielnie zarządza kolejnymi identyfikatorami.
                    conn.commit()

                # Aktualizacja widoku w interfejsie graficznym
                self.load_doctor_results()

                QMessageBox.information(
                    self,
                    'Sukces',
                    'Baza danych została pomyślnie wyczyszczona.'
                )
            except sqlite3.Error as db_error:
                QMessageBox.critical(
                    self,
                    'Błąd bazy danych',
                    f'Napotkano krytyczny błąd podczas operacji na bazie:\n{str(db_error)}'
                )


if __name__ == '__main__':
    init_db()
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())