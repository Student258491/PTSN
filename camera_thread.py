import cv2
import numpy as np
import mediapipe as mp
import math
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

class CameraMediaPipeThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    test_result_signal = pyqtSignal(str)

    def __init__(self, camera_id: int = 0, test_type: str = 'right_arm') -> None:
        super().__init__()
        self.camera_id: int = camera_id
        self.test_type: str = test_type
        self._run_flag: bool = True
        self.test_passed: bool = False

    def run(self) -> None:
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

                        # Diagnostic inference logic transitioned to if/elif for Python 3.9 compatibility
                        if not self.test_passed:
                            landmarks = results.pose_landmarks.landmark
                            r_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                            r_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
                            l_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                            l_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]

                            r_visible: bool = r_shoulder.visibility > 0.5 and r_wrist.visibility > 0.5
                            l_visible: bool = l_shoulder.visibility > 0.5 and l_wrist.visibility > 0.5
                            passed: bool = False

                            if self.test_type == 'right_arm' and r_visible and r_wrist.y < r_shoulder.y:
                                passed = True
                            elif self.test_type == 'left_arm' and l_visible and l_wrist.y < l_shoulder.y:
                                passed = True
                            elif self.test_type == 'both_arms' and r_visible and l_visible and r_wrist.y < r_shoulder.y and l_wrist.y < l_shoulder.y:
                                passed = True
                            elif self.test_type == 'hands_together' and r_visible and l_visible:
                                dist = math.hypot(r_wrist.x - l_wrist.x, r_wrist.y - l_wrist.y)
                                if dist < 0.05:
                                    passed = True

                            if passed:
                                self.test_passed = True
                                self.test_result_signal.emit("Sukces: Zadanie wykonane poprawnie.")

                    final_frame = np.require(image_rgb, dtype=np.uint8, requirements=['C_CONTIGUOUS'])
                    h, w, ch = final_frame.shape
                    bytes_per_line = ch * w

                    q_img = QImage(final_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
                    self.change_pixmap_signal.emit(q_img)

                except Exception:
                    pass

                QThread.msleep(30)
        cap.release()

    def stop(self) -> None:
        self._run_flag = False
        self.wait()