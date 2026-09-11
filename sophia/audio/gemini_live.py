"""
Sophia Gemini Live Multimodal Voice Engine
Full-Duplex, Real-Time Bidirectional Native Audio Streaming with Aoede Voice.
Features non-blocking audio channels, on-demand activation, auto-standby mute,
and complete coexistence with system media (YouTube, Spotify, calls).
"""

import asyncio
import logging
import queue
import time
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from google.genai import types

from sophia.config import config, get_genai_client
from sophia.core.persona import SOPHIA_SYSTEM_PROMPT
from sophia.ui.notch_bridge import notch_bridge

logger = logging.getLogger("SophiaGeminiLive")


class GeminiLiveSession:
    """Manages full-duplex live audio conversation with Gemini Live and Aoede voice."""

    def __init__(self, voice_name: Optional[str] = None):
        self.voice_name = voice_name or config.gcp.live_voice_name  # "Aoede"
        self.model = config.gcp.live_model  # "gemini-live-2.5-flash-native-audio"
        self.is_running = False
        self.input_sample_rate = 16000
        self.output_sample_rate = 24000
        self.audio_out_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.last_activity_time = time.time()
        self.idle_timeout_seconds = 12.0  # Auto-reverts to standby mute after 12s of idle

    def _build_config(self) -> types.LiveConnectConfig:
        """Constructs configuration for low-latency native audio streaming with Aoede/Kore voice."""
        persona_desc = (
            "breezy, charming, natural, confident, and warm"
            if self.voice_name == "Aoede"
            else "calm, poised, elegant, soothing, and sophisticated"
        )
        system_instruction = (
            f"{SOPHIA_SYSTEM_PROMPT}\n\n"
            "You are speaking live to your creator Saaransh through your native audio stream. "
            f"Your voice persona is {self.voice_name}: {persona_desc}. "
            "Speak naturally and concisely, with real conversational inflection. "
            "Acknowledge prompts with affirmative grace ('Yes sir?', 'Right away, sir')."
        )

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice_name
                    )
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_instruction)]
            )
        )

    async def start_session(self, initial_prompt: Optional[str] = None):
        """
        Starts an on-demand live conversational session.
        Automatically releases all audio resources and returns to standby mute when idle.
        """
        if self.is_running:
            logger.debug("Live session already active.")
            return

        self.is_running = True
        self.last_activity_time = time.time()
        client = get_genai_client()
        live_config = self._build_config()

        logger.info("Activating Gemini Live on-demand with voice '%s'...", self.voice_name)
        await notch_bridge.connect()
        await notch_bridge.set_state("listening")
        await notch_bridge.set_status(f"Live ({self.voice_name})")

        try:
            async with client.aio.live.connect(model=self.model, config=live_config) as session:
                logger.info("Connected to Gemini Live session.")

                # If an explicit initial prompt was provided, send it
                if initial_prompt:
                    await session.send_client_content(
                        turns=[types.Content(parts=[types.Part.from_text(text=initial_prompt)])],
                        turn_complete=True
                    )

                # Parallel tasks: audio receiver, on-demand player, mic sender, idle watcher
                player_task = asyncio.create_task(self._play_audio_loop())
                recv_task = asyncio.create_task(self._receive_from_gemini(session))
                mic_task = asyncio.create_task(self._stream_mic_to_gemini(session))
                watcher_task = asyncio.create_task(self._idle_watcher())

                await asyncio.gather(player_task, recv_task, mic_task, watcher_task)

        except asyncio.CancelledError:
            logger.info("Live session ended.")
        except Exception as e:
            logger.error("Live session notice: %s", e)
        finally:
            self.is_running = False
            # Clear output queue to free memory
            while not self.audio_out_queue.empty():
                try:
                    self.audio_out_queue.get_nowait()
                except Exception:
                    break
            await notch_bridge.set_state("idle")
            await notch_bridge.set_status("Ready (Muted)")
            logger.info("Sophia returned to standby mute. Audio channels 100% free.")

    async def _idle_watcher(self):
        """Watches for inactivity and automatically puts Sophia into standby mute to free audio."""
        while self.is_running:
            await asyncio.sleep(1.0)
            if time.time() - self.last_activity_time > self.idle_timeout_seconds:
                logger.info("Inactivity timeout reached (%ds). Reverting to standby mute.", self.idle_timeout_seconds)
                self.is_running = False
                break

    async def _stream_mic_to_gemini(self, session):
        """Streams microphone PCM audio chunks to Gemini Live only while session is active."""
        loop = asyncio.get_running_loop()
        chunk_samples = int(self.input_sample_rate * 0.1)  # 100ms chunks
        mic_queue: queue.Queue[bytes] = queue.Queue()

        def mic_callback(indata, frames, time_info, status):
            if self.is_running:
                mic_queue.put(bytes(indata))

        # Open non-exclusive shared input stream
        with sd.RawInputStream(
            samplerate=self.input_sample_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_samples,
            callback=mic_callback
        ):
            logger.debug("Microphone stream opened for live session.")
            while self.is_running:
                try:
                    chunk = await loop.run_in_executor(None, mic_queue.get, True, 0.4)
                    if chunk:
                        pcm_arr = np.frombuffer(chunk, dtype=np.int16)
                        energy = np.sqrt(np.mean(pcm_arr.astype(np.float32)**2))
                        if energy > 450:
                            self.last_activity_time = time.time()
                            await notch_bridge.set_state("listening")

                        await session.send_realtime_input(
                            audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                        )
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.debug("Mic sender finished: %s", e)
                    break
        logger.debug("Microphone stream closed.")

    async def _receive_from_gemini(self, session):
        """Receives streaming native audio chunks from Gemini Live."""
        try:
            async for response in session.receive():
                if not self.is_running:
                    break

                server_content = response.server_content
                if server_content is not None:
                    # User interruption (barge-in)
                    if getattr(server_content, "interrupted", False):
                        logger.info("Interruption detected: clearing audio queue.")
                        while not self.audio_out_queue.empty():
                            try:
                                self.audio_out_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        await notch_bridge.set_state("listening")
                        continue

                    model_turn = server_content.model_turn
                    if model_turn is not None:
                        for part in model_turn.parts:
                            if hasattr(part, "text") and part.text:
                                await notch_bridge.set_transcript(part.text)
                            if part.inline_data and part.inline_data.data:
                                self.last_activity_time = time.time()
                                await notch_bridge.set_state("speaking")
                                await self.audio_out_queue.put(part.inline_data.data)

                    if getattr(server_content, "turn_complete", False):
                        self.last_activity_time = time.time()
                        logger.debug("Turn complete from Gemini Live.")
        except Exception as e:
            logger.debug("Live receiver terminated: %s", e)

    async def _play_audio_loop(self):
        """
        Dynamically opens the 24kHz speaker output stream ONLY when audio chunks arrive,
        and closes it immediately when idle to prevent blocking system media or YouTube.
        """
        loop = asyncio.get_running_loop()

        while self.is_running:
            try:
                # Wait for next audio chunk
                chunk = await asyncio.wait_for(self.audio_out_queue.get(), timeout=0.3)
            except asyncio.TimeoutError:
                continue

            # Open output stream dynamically only for the duration of playback
            try:
                with sd.RawOutputStream(
                    samplerate=self.output_sample_rate,
                    channels=1,
                    dtype="int16",
                ) as out_stream:
                    logger.debug("Speaker stream opened for playback.")
                    await loop.run_in_executor(None, out_stream.write, chunk)

                    # Drain remaining continuous chunks
                    while self.is_running:
                        try:
                            next_chunk = self.audio_out_queue.get_nowait()
                            await loop.run_in_executor(None, out_stream.write, next_chunk)
                        except asyncio.QueueEmpty:
                            # Let remaining buffer flush
                            await asyncio.sleep(0.1)
                            break
            except Exception as e:
                logger.debug("Speaker stream error: %s", e)

            # Once active audio speech finishes, stay in listening mode if session is active
            if self.is_running:
                await notch_bridge.set_state("listening")

    def stop(self):
        self.is_running = False

    async def switch_voice(self, new_voice: str):
        """Switches voice persona and activates Gemini Live in the new voice."""
        self.voice_name = new_voice
        config.gcp.live_voice_name = new_voice
        logger.info("Switched Gemini Live voice to: %s", new_voice)

        if self.is_running:
            self.stop()
            await asyncio.sleep(0.3)

        # Launch live session speaking in the new voice!
        await self.start_session(
            initial_prompt=f"Acknowledge in one short charming sentence that you are now speaking with your {new_voice} voice persona."
        )


# Singleton instance
gemini_live_session = GeminiLiveSession()
