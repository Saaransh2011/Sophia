"""
Screen Perception Engine
Captures macOS screen, detects active applications/windows, and analyzes visual context with Gemini Vision.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from sophia.config import config

logger = logging.getLogger("SophiaScreenVision")


class ScreenVision:
    """Provides visual perception of the user's active screen."""

    def __init__(self):
        self.screenshot_path = Path("/tmp/sophia_screen.jpg")

    async def capture_screen(self) -> Optional[Path]:
        """Takes a silent screenshot using macOS native screencapture."""
        try:
            cmd = ["screencapture", "-x", "-C", "-t", "jpg", str(self.screenshot_path)]
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()
            if proc.returncode == 0 and self.screenshot_path.exists():
                return self.screenshot_path
        except Exception as e:
            logger.error("Screenshot capture failed: %s", e)
        return None

    async def get_active_app(self) -> Dict[str, str]:
        """Gets the frontmost application and window title on macOS."""
        script = """
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set appName to name of frontApp
            try
                set winTitle to name of front window of frontApp
            on error
                set winTitle to ""
            end try
            return appName & "|||" & winTitle
        end tell
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_b, _ = await proc.communicate()
            output = stdout_b.decode("utf-8").strip()
            if "|||" in output:
                app_name, win_title = output.split("|||", 1)
                return {"app": app_name.strip(), "window": win_title.strip()}
        except Exception as e:
            logger.debug("Failed to get active app: %s", e)
        return {"app": "Unknown", "window": ""}

    async def analyze_screen(self, user_prompt: str = "Describe what is currently visible on my screen.") -> str:
        """Analyzes active screen using Gemini Vision."""
        img_path = await self.capture_screen()
        if not img_path:
            return "Unable to capture screen."

        active_info = await self.get_active_app()

        try:
            from sophia.config import get_genai_client
            from google.genai import types

            client = get_genai_client()
            with open(img_path, "rb") as f:
                image_bytes = f.read()

            prompt = (
                f"You are Sophia, the user's personal assistant on macOS. "
                f"Active Application: {active_info.get('app')}, Window: {active_info.get('window')}. "
                f"User Question: {user_prompt}"
            )

            response = client.models.generate_content(
                model=config.gcp.gemini_model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ]
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Screen analysis error: %s", e)
            return f"Visual analysis encountered an error: {e}"


# Singleton instance
screen_vision = ScreenVision()
