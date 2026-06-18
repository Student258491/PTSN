import cv2
import numpy as np
import mediapipe as mp
import math
import time
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage


class CameraMediaPipeThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    test_result_signal = pyqtSignal(str)

    def __init__(self, camera_id: int = 0, test_type: str = 'barre_test') -> None:
        super().__init__()
        self.camera_id: int = camera_id
        self.test_type: str = test_type
        self._run_flag: bool = True
        self.test_passed: bool = False

        self.start_time: Optional[float] = None
        self.test_stage: int = 0

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

                        if not self.test_passed:
                            landmarks = results.pose_landmarks.landmark

                            nose = landmarks[mp_pose.PoseLandmark.NOSE]
                            r_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                            l_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                            r_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
                            l_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
                            r_index = landmarks[mp_pose.PoseLandmark.RIGHT_INDEX]
                            l_index = landmarks[mp_pose.PoseLandmark.LEFT_INDEX]

                            core_visible = r_shoulder.visibility > 0.5 and l_shoulder.visibility > 0.5 and nose.visibility > 0.5
                            passed = False

                            if self.test_type == 'barre_test' and core_visible:
                                if r_wrist.visibility > 0.5 and l_wrist.visibility > 0.5:
                                    arms_extended = (abs(r_wrist.y - r_shoulder.y) < 0.15) and (
                                                abs(l_wrist.y - l_shoulder.y) < 0.15)

                                    if arms_extended:
                                        if self.start_time is None:
                                            self.start_time = time.time()
                                        elif time.time() - self.start_time >= 5.0:
                                            passed = True
                                    else:
                                        self.start_time = None

                            elif self.test_type == 'finger_to_nose_right' and core_visible and r_index.visibility > 0.5:
                                dist_to_nose = math.hypot(r_index.x - nose.x, r_index.y - nose.y)
                                dist_to_shoulder = math.hypot(r_index.x - r_shoulder.x, r_index.y - r_shoulder.y)

                                if self.test_stage == 0 and dist_to_shoulder > 0.25:
                                    self.test_stage = 1

                                elif self.test_stage == 1 and dist_to_nose < 0.07:
                                    passed = True

                            elif self.test_type == 'finger_to_nose_left' and core_visible and l_index.visibility > 0.5:
                                dist_to_nose = math.hypot(l_index.x - nose.x, l_index.y - nose.y)
                                dist_to_shoulder = math.hypot(l_index.x - l_shoulder.x, l_index.y - l_shoulder.y)

                                if self.test_stage == 0 and dist_to_shoulder > 0.25:
                                    self.test_stage = 1

                                elif self.test_stage == 1 and dist_to_nose < 0.07:
                                    passed = True

                            if passed:
                                self.test_passed = True
                                self.test_result_signal.emit(
                                    f"Sukces: {self.test_type.replace('_', ' ').upper()} zaliczony poprawnie.")

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
