"""
Sophia Live Conversational Voice Loop
Orchestrates continuous voice interaction:
1. Microphone streaming & VAD
2. Google Cloud Speech-to-Text
3. Gemini 2.5 Pro Multi-Turn Conversational Reasoning
4. Dynamic Island Notch UI updates
5. Google Cloud Journey-F Neural Voice playback
"""

import asyncio
import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

import numpy as np

from sophia.audio.sound_effects import sound_effects
from sophia.config import config
from sophia.core.conversational_engine import conversational_engine
from sophia.ui.notch_bridge import notch_bridge

logger = logging.getLogger("SophiaVoiceLoop")


class LiveVoiceLoop:
    """Manages the full-duplex conversational voice loop."""

    def __init__(self):
        self.is_active = False
        self.sample_rate = config.audio.sample_rate
        self.channels = config.audio.channels

    async def record_phrase(self, max_duration: float = 8.0, silence_threshold: float = 0.015) -> Optional[bytes]:
        """
        Records a single voice phrase from the microphone with energy-based Voice Activity Detection.
        """
        import sounddevice as sd

        logger.info("Listening for user voice...")
        await notch_bridge.set_state("listening")
        await notch_bridge.set_status("Listening...")

        loop = asyncio.get_running_loop()
        buffer = []
        silence_counter = 0
        has_spoken = False

        chunk_duration = 0.1  # 100ms chunks
        chunk_samples = int(self.sample_rate * chunk_duration)

        def sync_record():
            nonlocal silence_counter, has_spoken
            with sd.InputStream(samplerate=self.sample_rate, channels=self.channels, dtype="float32") as stream:
                total_time = 0.0
                while total_time < max_duration:
                    data, _ = stream.read(chunk_samples)
                    energy = np.sqrt(np.mean(data**2))
                    buffer.append(data.copy())
                    total_time += chunk_duration

                    if energy > silence_threshold:
                        has_spoken = True
                        silence_counter = 0
                    elif has_spoken:
                        silence_counter += 1
                        # 1.2 seconds of silence after speech indicates user finished speaking
                        if silence_counter > 12:
                            break

        try:
            await loop.run_in_executor(None, sync_record)
        except Exception as e:
            logger.error("Microphone recording error: %s", e)
            return None

        if not buffer or not has_spoken:
            logger.debug("No speech detected.")
            return None

        # Concatenate audio chunks
        full_audio = np.concatenate(buffer, axis=0)
        # Convert float32 to int16 PCM
        pcm_data = (full_audio * 32767).astype(np.int16)

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data.tobytes())

        return wav_io.getvalue()

    async def transcribe_speech(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribes recorded audio using Google Cloud Speech-to-Text."""
        try:
            from google.cloud import speech

            cred_path = Path(config.gcp.credentials_path)
            if cred_path.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)

            client = speech.SpeechClient()
            audio = speech.RecognitionAudio(content=audio_bytes)
            speech_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                language_code="en-US",
                model="latest_long",
                enable_automatic_punctuation=True,
            )

            response = client.recognize(config=speech_config, audio=audio)
            for result in response.results:
                transcript = result.alternatives[0].transcript
                if transcript.strip():
                    logger.info("Transcribed user: '%s'", transcript)
                    return transcript.strip()
        except Exception as e:
            logger.error("Speech-to-Text transcription error: %s", e)

        return None

    async def run_conversational_turn(self, transcribed_text: Optional[str] = None):
        """
        Executes one full conversational turn:
        1. Listens and transcribes (if text not provided)
        2. Queries Gemini 2.5 Pro multi-turn session
        3. Updates Dynamic Island Notch UI
        4. Synthesizes and plays Google Cloud Journey neural voice
        """
        user_input = transcribed_text
        if not user_input:
            audio = await self.record_phrase()
            if not audio:
                await notch_bridge.set_state("idle")
                return
            user_input = await self.transcribe_speech(audio)

        if not user_input:
            await notch_bridge.set_state("idle")
            return

        # Update Island UI
        await notch_bridge.set_state("thinking")
        await notch_bridge.set_status("Thinking...")
        await notch_bridge.set_transcript(f"User: {user_input}")

        # Send to Gemini 2.5 Pro
        reply = await conversational_engine.send_message(user_input)

        # Update Island UI to speaking
        await notch_bridge.set_state("speaking")
        await notch_bridge.set_status(reply[:45] + ("..." if len(reply) > 45 else ""))
        await notch_bridge.set_transcript(reply)

        # Speak reply with Google Cloud Journey neural voice
        await sound_effects.speak(reply)

        # Revert to idle
        await notch_bridge.set_state("idle")

    async def start_interactive_session(self, initial_prompt: Optional[str] = None):
        """Starts an ongoing conversational session with Sophia."""
        logger.info("Starting live conversational session with Sophia...")
        await sound_effects.play_chime("ready")

        if initial_prompt:
            await self.run_conversational_turn(transcribed_text=initial_prompt)

        # Continue conversational listening loop
        self.is_active = True
        while self.is_active:
            await self.run_conversational_turn()
            await asyncio.sleep(0.5)

    def stop(self):
        self.is_active = False


# Singleton instance
live_voice_loop = LiveVoiceLoop()
