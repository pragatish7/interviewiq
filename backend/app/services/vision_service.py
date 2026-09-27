"""
Video vision service for non-verbal analysis.
Uses OpenCV and MediaPipe when available, falls back to metadata-based analysis.
"""
import os
import logging
import math
from typing import Dict, Any, List as TypingList, Optional

logger = logging.getLogger(__name__)

USE_OPENCV = False
USE_MEDIAPIPE = False

try:
    import cv2
    USE_OPENCV = True
except ImportError:
    logger.info("OpenCV not available for video analysis")

try:
    import mediapipe as mp
    USE_MEDIAPIPE = True
except ImportError:
    logger.info("MediaPipe not available for face/pose analysis")


def analyze_video_nonverbal(video_path: str, duration: float) -> Dict[str, Any]:
    """
    Analyze non-verbal aspects from video.
    Returns observable video indicators only.
    """
    result = {
        "face_visibility": 70.0,
        "camera_presence": 70.0,
        "head_movement_score": 70.0,
        "framing_score": 70.0,
        "excessive_movement": False,
        "face_detection_rate": 0.0,
        "analyzed_frames": 0,
        "details": {},
        "method": "metadata",
    }

    if not USE_OPENCV or not os.path.exists(video_path):
        return result

    try:
        return _analyze_with_opencv(video_path, duration)
    except Exception as e:
        logger.warning(f"OpenCV analysis failed: {e}")
        return result


def _analyze_with_opencv(video_path: str, duration: float) -> Dict[str, Any]:
    """Analyze video using OpenCV and optionally MediaPipe."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return _default_result()

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if total_frames == 0:
        cap.release()
        return _default_result()

    sample_interval = max(1, int(fps * 2))  # Sample every 2 seconds
    frames_analyzed = 0
    face_detected_count = 0
    face_sizes = []
    head_positions = []
    motion_scores = []

    prev_frame = None
    face_cascade = None

    if USE_MEDIAPIPE:
        mp_face_detection = mp.solutions.face_detection
    else:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)

    frame_idx = 0
    max_frames_to_check = min(total_frames, int(fps * min(duration, 60)))

    while frame_idx < max_frames_to_check:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        frames_analyzed += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = []
        if USE_MEDIAPIPE:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with mp_face_detection.FaceDetection(
                model_selection=1, min_detection_confidence=0.5
            ) as face_detection:
                results = face_detection.process(rgb)
                if results.detections:
                    for detection in results.detections:
                        bbox = detection.location_data.relative_bounding_box
                        fx = int(bbox.xmin * width)
                        fy = int(bbox.ymin * height)
                        fw = int(bbox.width * width)
                        fh = int(bbox.height * height)
                        faces.append((fx, fy, fw, fh))
        elif face_cascade is not None:
            detected = face_cascade.detectMultiScale(gray, 1.3, 5)
            faces = detected.tolist() if len(detected) > 0 else []

        if faces:
            face_detected_count += 1
            largest = max(faces, key=lambda f: f[2] * f[3] if len(f) >= 4 else 0)
            if len(largest) >= 4:
                fx, fy, fw, fh = largest
                face_sizes.append((fw * fh) / (width * height))
                head_positions.append((fx + fw / 2, fy + fh / 2))

        # Motion detection
        if prev_frame is not None:
            diff = cv2.absdiff(prev_frame, gray)
            motion = cv2.mean(diff)[0]
            motion_scores.append(motion)

        prev_frame = gray.copy()
        frame_idx += sample_interval

    cap.release()

    # Compute scores
    face_visibility = (face_detected_count / max(frames_analyzed, 1)) * 100

    # Face size consistency
    if face_sizes:
        mean_size = sum(face_sizes) / len(face_sizes)
        size_variance = sum((s - mean_size) ** 2 for s in face_sizes) / len(face_sizes)
        face_size_score = max(0, min(100, 100 - size_variance * 5000))
    else:
        face_size_score = 60

    # Head position consistency (looking at camera)
    if head_positions and len(head_positions) >= 2:
        x_positions = [p[0] for p in head_positions]
        y_positions = [p[1] for p in head_positions]
        x_var = sum((x - sum(x_positions) / len(x_positions)) ** 2 for x in x_positions) / len(x_positions)
        y_var = sum((y - sum(y_positions) / len(y_positions)) ** 2 for y in y_positions) / len(y_positions)
        center_deviation = math.sqrt(x_var + y_var) / max(width, height)
        camera_presence = max(40, min(100, 100 - center_deviation * 200))
    else:
        camera_presence = 65

    # Head movement score
    if head_positions and len(head_positions) >= 3:
        movements = []
        for i in range(1, len(head_positions)):
            dx = head_positions[i][0] - head_positions[i - 1][0]
            dy = head_positions[i][1] - head_positions[i - 1][1]
            movements.append(math.sqrt(dx * dx + dy * dy))
        avg_movement = sum(movements) / len(movements)
        excessive = avg_movement > width * 0.1
        head_movement_score = max(30, min(100, 100 - avg_movement / width * 100))
    else:
        excessive = False
        head_movement_score = 70

    # Framing score based on video dimensions
    if width > 0 and height > 0:
        aspect_ratio = width / height
        if 0.9 <= aspect_ratio <= 1.2:
            framing_score = 90
        elif 0.7 <= aspect_ratio <= 1.5:
            framing_score = 75
        else:
            framing_score = 60

        if width >= 1280:
            framing_score += 5
    else:
        framing_score = 65

    # Overall camera presence
    camera_presence = round(
        (face_visibility * 0.3 + face_size_score * 0.25 + camera_presence * 0.25 + framing_score * 0.2),
        1
    )

    return {
        "face_visibility": round(min(100, face_visibility), 1),
        "camera_presence": round(min(100, camera_presence), 1),
        "head_movement_score": round(min(100, head_movement_score), 1),
        "framing_score": round(min(100, framing_score), 1),
        "excessive_movement": excessive,
        "face_detection_rate": round(face_visibility, 1),
        "analyzed_frames": frames_analyzed,
        "method": "mediapipe" if USE_MEDIAPIPE else "opencv",
        "video_info": {
            "width": width,
            "height": height,
            "fps": round(fps, 2),
        },
    }


def _default_result() -> Dict[str, Any]:
    return {
        "face_visibility": 65.0,
        "camera_presence": 65.0,
        "head_movement_score": 70.0,
        "framing_score": 65.0,
        "excessive_movement": False,
        "face_detection_rate": 0.0,
        "analyzed_frames": 0,
        "method": "unavailable",
    }
