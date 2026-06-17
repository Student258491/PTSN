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