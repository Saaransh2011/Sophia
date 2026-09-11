"""
Audio Feedback & Speech Output
Handles macOS system chimes and voice synthesis (local neural voice or Google Cloud TTS).
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("SophiaAudioEffects")


class SoundEffects:
    """Plays system sounds and vocal replies."""

    SYSTEM_SOUNDS = {
        "wake": "/System/Library/Sounds/Ping.aiff",
        "ready": "/System/Library/Sounds/Glass.aiff",
        "action": "/System/Library/Sounds/Tink.aiff",
        "error": "/System/Library/Sounds/Basso.aiff",
    }

    @classmethod
    async def play_chime(cls, sound_name: str = "wake"):
        """Plays a native macOS system sound asynchronously."""
        sound_path = cls.SYSTEM_SOUNDS.get(sound_name, cls.SYSTEM_SOUNDS["wake"])
        if os.path.exists(sound_path):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "afplay", sound_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                await proc.communicate()
            except Exception as e:
                logger.debug("Failed to play chime: %s", e)

    @classmethod
    async def speak(cls, text: str, voice: str = "Samantha"):
        """
        Speaks text using macOS native speech synthesizer.
        Provides sub-second local response time.
        """
        logger.info("Sophia speaking: %s", text)
        try:
            # -v Samantha (clear, charming female voice), -r rate (approx 190 wpm)
            proc = await asyncio.create_subprocess_exec(
                "say", "-v", voice, "-r", "195", text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            await proc.communicate()
        except Exception as e:
            logger.error("Local speech synthesis error: %s", e)


sound_effects = SoundEffects()
