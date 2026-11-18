from __future__ import annotations

import cv2
import numpy as np

HALF_WIDTH_RATIO = 0.17
HALF_HEIGHT_RATIO = 0.10
MIN_PATCH_SIDE = 6


class EyeStateDetector:
    def openness(self, frame: np.ndarray, face: np.ndarray) -> float:
        width = float(face[2])
        half_w = max(MIN_PATCH_SIDE, int(width * HALF_WIDTH_RATIO))
        half_h = max(MIN_PATCH_SIDE, int(width * HALF_HEIGHT_RATIO))
        frame_height, frame_width = frame.shape[:2]
        contrasts: list[float] = []
        for index in (4, 6):
            center_x, center_y = int(face[index]), int(face[index + 1])
            left, right = max(center_x - half_w, 0), min(center_x + half_w, frame_width)
            top, bottom = max(center_y - half_h, 0), min(center_y + half_h, frame_height)
            if right - left < MIN_PATCH_SIDE or bottom - top < MIN_PATCH_SIDE:
                continue
            gray = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
            contrasts.append(float(blurred.std()) / max(float(blurred.mean()), 1.0))
        return float(np.mean(contrasts)) if contrasts else 0.0
