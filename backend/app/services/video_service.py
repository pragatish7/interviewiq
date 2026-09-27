"""
Video service - handles video file operations, audio extraction, and video metadata.
"""
import os
import subprocess
import json
import shutil
import tempfile
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def _find_binary(name: str) -> Optional[str]:
    """Locate ffmpeg/ffprobe: system PATH first, then imageio-ffmpeg's bundled copy."""
    exe = shutil.which(name)
    if exe:
        return exe
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as e:
            logger.warning(f"imageio_ffmpeg unavailable: {e}")
    return None


def _ffmpeg() -> str:
    return _find_binary("ffmpeg") or "ffmpeg"


def _ffprobe() -> Optional[str]:
    return _find_binary("ffprobe")


def _cv2_duration(video_path: str) -> float:
    """Fallback duration probe using OpenCV when ffprobe is unavailable."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0.0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        return float(frames / fps) if fps > 0 and frames > 0 else 0.0
    except Exception:
        return 0.0


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe (or OpenCV fallback)."""
    probe = _ffprobe()
    if probe is None:
        return _cv2_duration(video_path)
    try:
        cmd = [probe, "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info.get("format", {}).get("duration", 0))
            if duration > 0:
                return duration
    except Exception as e:
        logger.warning(f"Could not get video duration: {e}")
    return _cv2_duration(video_path)


def get_video_info(video_path: str) -> Dict[str, Any]:
    """Get comprehensive video metadata."""
    info = {
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "codec": "unknown",
        "has_audio": False,
        "audio_codec": None,
        "bitrate": 0,
    }
    probe = _ffprobe()
    try:
        if probe:
            cmd = [probe, "-v", "quiet", "-print_format", "json",
                   "-show_format", "-show_streams", video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                fmt = data.get("format", {})
                info["duration"] = float(fmt.get("duration", 0))
                info["bitrate"] = int(fmt.get("bit_rate", 0))

                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        info["width"] = stream.get("width", 0)
                        info["height"] = stream.get("height", 0)
                        info["codec"] = stream.get("codec_name", "unknown")
                        r_frame_rate = stream.get("r_frame_rate", "0/1")
                        if "/" in r_frame_rate:
                            num, den = r_frame_rate.split("/")
                            if int(den) > 0:
                                info["fps"] = round(int(num) / int(den), 2)
                    elif stream.get("codec_type") == "audio":
                        info["has_audio"] = True
                        info["audio_codec"] = stream.get("codec_name", "unknown")
    except Exception as e:
        logger.warning(f"Could not get video info: {e}")

    # Fall back to OpenCV when ffprobe is unavailable
    if info["duration"] <= 0 or info["width"] <= 0:
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                info["fps"] = round(cap.get(cv2.CAP_PROP_FPS) or 0, 2)
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                if info["fps"] > 0 and frames > 0:
                    info["duration"] = round(frames / info["fps"], 2)
                info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                cap.release()
        except Exception:
            pass
    return info


def extract_audio(video_path: str, output_path: Optional[str] = None) -> Tuple[Optional[str], float]:
    """
    Extract audio from video file.
    Returns (audio_path, duration).
    """
    if output_path is None:
        base = os.path.splitext(video_path)[0]
        output_path = base + ".wav"

    duration = get_video_duration(video_path)

    ffmpeg = _ffmpeg()
    try:
        cmd = [ffmpeg, "-y", "-i", video_path,
               "-vn", "-acodec", "pcm_s16le",
               "-ar", "16000", "-ac", "1",
               output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path, duration
        else:
            logger.error(f"ffmpeg error: {result.stderr[:500]}")
    except FileNotFoundError:
        logger.error("ffmpeg not found. Please install ffmpeg.")
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")

    return None, duration


def extract_frames(video_path: str, output_dir: str, interval: float = 5.0, max_frames: int = 20) -> list:
    """Extract key frames from video for non-verbal analysis."""
    os.makedirs(output_dir, exist_ok=True)
    frames = []
    try:
        duration = get_video_duration(video_path)
        if duration <= 0:
            return frames

        actual_interval = max(interval, duration / max_frames)
        ffmpeg = _ffmpeg()
        cmd = [ffmpeg, "-y", "-i", video_path,
               "-vf", f"fps=1/{actual_interval}",
               "-frames:v", str(max_frames),
               os.path.join(output_dir, "frame_%03d.jpg")]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode == 0:
            for f in sorted(os.listdir(output_dir)):
                if f.endswith(".jpg"):
                    frames.append(os.path.join(output_dir, f))
    except Exception as e:
        logger.warning(f"Frame extraction failed: {e}")
    return frames


def cleanup_temp_files(*paths):
    """Clean up temporary files."""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
