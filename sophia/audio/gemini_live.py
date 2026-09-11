"""
Sophia Gemini Live Multimodal Voice Engine
Full-Duplex, Real-Time Bidirectional Native Audio Streaming with Aoede Voice.
Powered by Google Cloud Vertex AI gemini-live-2.5-flash-native-audio.
"""

import asyncio
import logging
import queue
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
        self.voice_name = voice_name or config.gcp.live_voice_name  # "Aoede" (charming female voice)
        self.model = config.gcp.live_model  # "gemini-live-2.5-flash-native-audio"
        self.is_running = False
        self.input_sample_rate = 16000
        self.output_sample_rate = 24000
        self.audio_out_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.current_out_stream: Optional[sd.RawOutputStream] = None

    def _build_config(self) -> types.LiveConnectConfig:
        """Constructs configuration for low-latency native audio streaming with Aoede voice."""
        system_instruction = (
            f"{SOPHIA_SYSTEM_PROMPT}\n\n"
            "You are speaking live to your creator Saaransh through your native audio stream. "
            "Your voice is Aoede: charming, poised, elegant, confident, and warm. "
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

    async def start_session(self):
        """Starts real-time live conversational stream connecting mic and speakers directly to Gemini Live."""
        self.is_running = True
        client = get_genai_client()
        live_config = self._build_config()

        logger.info("Connecting to Gemini Live (%s) with voice '%s'...", self.model, self.voice_name)
        await notch_bridge.connect()
        await notch_bridge.set_state("listening")
        await notch_bridge.set_status("Sophia Live: Connecting...")

        try:
            async with client.aio.live.connect(model=self.model, config=live_config) as session:
                logger.info("Connected to Gemini Live session.")
                await notch_bridge.set_status(f"Live Online ({self.voice_name})")

                # Send initial greeting prompt so Sophia greets the user live
                await session.send_client_content(
                    turns=[types.Content(parts=[types.Part.from_text(text="Sophia, warmly greet your creator Saaransh and let him know you are online and listening live.")])],
                    turn_complete=True
                )

                # Run parallel tasks: audio receiver, audio player, mic sender
                player_task = asyncio.create_task(self._play_audio_loop())
                recv_task = asyncio.create_task(self._receive_from_gemini(session))
                mic_task = asyncio.create_task(self._stream_mic_to_gemini(session))

                await asyncio.gather(player_task, recv_task, mic_task)

        except asyncio.CancelledError:
            logger.info("Live session cancelled.")
        except Exception as e:
            logger.error("Error in Gemini Live session: %s", e)
        finally:
            self.is_running = False
            await notch_bridge.set_state("idle")

    async def _stream_mic_to_gemini(self, session):
        """Streams microphone PCM audio chunks to Gemini Live in real-time."""
        loop = asyncio.get_running_loop()
        chunk_samples = int(self.input_sample_rate * 0.1)  # 100ms chunks

        mic_queue: queue.Queue[bytes] = queue.Queue()

        def mic_callback(indata, frames, time_info, status):
            if self.is_running:
                mic_queue.put(bytes(indata))

        with sd.RawInputStream(
            samplerate=self.input_sample_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_samples,
            callback=mic_callback
        ):
            logger.info("Microphone stream active (16kHz)...")
            while self.is_running:
                try:
                    # Non-blocking get with executor
                    chunk = await loop.run_in_executor(None, mic_queue.get, True, 0.5)
                    if chunk:
                        # Energy check for UI state
                        pcm_arr = np.frombuffer(chunk, dtype=np.int16)
                        energy = np.sqrt(np.mean(pcm_arr.astype(np.float32)**2))
                        if energy > 400:
                            await notch_bridge.set_state("listening")

                        await session.send_realtime_input(
                            audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                        )
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.debug("Mic sender error: %s", e)
                    break

    async def _receive_from_gemini(self, session):
        """Receives streaming native audio chunks from Gemini Live."""
        try:
            async for response in session.receive():
                server_content = response.server_content
                if server_content is not None:
                    # Handle user interruption (barge-in)
                    if getattr(server_content, "interrupted", False):
                        logger.info("User interrupted. Clearing audio queue...")
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
                            if part.inline_data and part.inline_data.data:
                                await notch_bridge.set_state("speaking")
                                await self.audio_out_queue.put(part.inline_data.data)

                    if getattr(server_content, "turn_complete", False):
                        logger.debug("Turn complete from Gemini Live.")
        except Exception as e:
            logger.error("Error receiving from Gemini Live: %s", e)

    async def _play_audio_loop(self):
        """Plays 24kHz audio chunks to speakers with minimal latency."""
        loop = asyncio.get_running_loop()

        with sd.RawOutputStream(
            samplerate=self.output_sample_rate,
            channels=1,
            dtype="int16",
        ) as out_stream:
            self.current_out_stream = out_stream
            logger.info("Speaker output stream active (24kHz)...")

            while self.is_running:
                try:
                    chunk = await asyncio.wait_for(self.audio_out_queue.get(), timeout=0.2)
                    await loop.run_in_executor(None, out_stream.write, chunk)
                except asyncio.TimeoutError:
                    if self.audio_out_queue.empty():
                        await notch_bridge.set_state("idle")
                except Exception as e:
                    logger.debug("Audio player error: %s", e)
                    break

    def stop(self):
        self.is_running = False


# Singleton instance
gemini_live_session = GeminiLiveSession()
