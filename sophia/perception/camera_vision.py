"""
Webcam & Object Perception
Captures frames from macOS webcam for object recognition, face presence, and user emotional state awareness.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

from sophia.config import config

logger = logging.getLogger("SophiaCameraVision")


class CameraVision:
    """Provides physical visual perception via macOS webcam."""

    def __init__(self):
        self.frame_path = Path("/tmp/sophia_camera.jpg")

    async def capture_frame(self) -> Optional[Path]:
        """
        Captures a single snapshot from the default webcam.
        Uses ffmpeg or imagesnap or AVFoundation if available.
        """
        # Try ffmpeg first if installed
        try:
            cmd = [
                "ffmpeg", "-y", "-f", "avfoundation", "-framerate", "30",
                "-video_size", "1280x720", "-i", "default", "-vframes", "1",
                str(self.frame_path)
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            await proc.communicate()
            if proc.returncode == 0 and self.frame_path.exists():
                return self.frame_path
        except Exception as e:
            logger.debug("ffmpeg camera capture attempt: %s", e)

        # Fallback: check imagesnap
        try:
            cmd = ["imagesnap", "-q", str(self.frame_path)]
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            if proc.returncode == 0 and self.frame_path.exists():
                return self.frame_path
        except Exception as e:
            logger.debug("imagesnap attempt: %s", e)

        return None

    async def identify_objects_or_emotion(self, query: str = "Identify what object is being shown to you or assess the user's expression.") -> str:
        """Analyzes camera frame with Gemini Vision."""
        img = await self.capture_frame()
        if not img:
            return "Camera feed is currently unavailable or requires permission."

        try:
            from google import genai
            from google.genai import types

            client = genai.Client()
            with open(img, "rb") as f:
                image_bytes = f.read()

            prompt = f"You are Sophia, looking through the MacBook camera. {query}"
            response = client.models.generate_content(
                model=config.gcp.gemini_model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ]
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Camera vision analysis failed: %s", e)
            return f"Error analyzing visual camera stream: {e}"


# Singleton instance
camera_vision = CameraVision()
