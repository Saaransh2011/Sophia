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
    async def speak(cls, text: str, voice: Optional[str] = None):
        """
        Speaks text using Google Cloud's premier Journey neural voice (en-US-Journey-F).
        Falls back to macOS native speech synthesizer if offline.
        """
        logger.info("Sophia vocalizing: %s", text)
        tts_audio = await cls._synthesize_google_tts(text)
        if tts_audio and tts_audio.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "afplay", str(tts_audio),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                await proc.communicate()
                return
            except Exception as e:
                logger.debug("afplay error: %s", e)

        # Fallback to local Samantha
        try:
            local_voice = voice or "Samantha"
            proc = await asyncio.create_subprocess_exec(
                "say", "-v", local_voice, "-r", "190", text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            await proc.communicate()
        except Exception as e:
            logger.error("Local fallback speech synthesis error: %s", e)

    @classmethod
    async def _synthesize_google_tts(cls, text: str) -> Optional[Path]:
        """Synthesizes high-fidelity conversational audio using Google Cloud Text-to-Speech."""
        try:
            from google.cloud import texttospeech
            from sophia.config import config

            cred_path = Path(config.gcp.credentials_path)
            if not cred_path.exists():
                return None

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
            client = texttospeech.TextToSpeechClient()

            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=config.gcp.tts_language_code,
                name=config.gcp.tts_voice_name,
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.03,
                pitch=0.0
            )

            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            cache_file = Path(f"/tmp/sophia_speech_{abs(hash(text)) % 1000000}.mp3")
            cache_file.write_bytes(response.audio_content)
            return cache_file
        except Exception as e:
            logger.debug("Google Cloud TTS synthesis failed: %s", e)
            return None


sound_effects = SoundEffects()
