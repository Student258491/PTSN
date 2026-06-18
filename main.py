import sys
from PyQt6.QtWidgets import QApplication
from gui import AppWindow

def main():
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    try:
        import mediapipe as mp
        test_pose = mp.solutions.pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        test_pose.close()
    except Exception as error:
        print(f"Błąd inicjalizacji MediaPipe: {error}")

    main()