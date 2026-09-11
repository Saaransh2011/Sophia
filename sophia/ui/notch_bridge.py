"""
Python Notch UI Bridge
Connects to the native Swift Dynamic Island Notch Overlay via Unix domain socket.
Sends visual state updates, transcript text, and receives user interactions (mute, vision toggles).
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from sophia.config import config, SOCKET_PATH

logger = logging.getLogger("SophiaNotchBridge")


class NotchBridge:
    """Manages IPC connection to the Swift Dynamic Island notch window."""

    def __init__(self, socket_path: Optional[str] = None):
        self.socket_path = socket_path or str(SOCKET_PATH)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected = False
        self.event_callbacks: list[Callable[[Dict[str, Any]], None]] = []
        self._listen_task: Optional[asyncio.Task] = None
        self._binary_proc: Optional[subprocess.Popen] = None

    def find_overlay_binary(self) -> Optional[Path]:
        """Finds compiled Swift SophiaNotchOverlay executable."""
        candidates = [
            Path(__file__).parent / "swift" / ".build" / "arm64-apple-macosx" / "debug" / "SophiaNotchOverlay",
            Path(__file__).parent / "swift" / ".build" / "debug" / "SophiaNotchOverlay",
            Path(__file__).parent / "swift" / ".build" / "release" / "SophiaNotchOverlay",
        ]
        for p in candidates:
            if p.exists() and os.access(p, os.X_OK):
                return p
        return None

    def ensure_overlay_running(self):
        """Starts Swift Dynamic Island overlay process if not running."""
        binary = self.find_overlay_binary()
        if not binary:
            logger.warning("SophiaNotchOverlay binary not compiled yet.")
            return

        # Check if already running
        import psutil
        for p in psutil.process_iter(["name"]):
            if p.info["name"] == "SophiaNotchOverlay":
                logger.debug("SophiaNotchOverlay is already running.")
                return

        logger.info("Launching Sophia Dynamic Island overlay: %s", binary)
        self._binary_proc = subprocess.Popen(
            [str(binary)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def connect(self, retries: int = 5, delay: float = 0.5) -> bool:
        """Connects to the Swift UI socket."""
        self.ensure_overlay_running()

        for attempt in range(retries):
            if os.path.exists(self.socket_path):
                try:
                    self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
                    self.is_connected = True
                    logger.info("Connected to Sophia Dynamic Island Notch UI.")
                    self._listen_task = asyncio.create_task(self._listen_events())
                    return True
                except Exception as e:
                    logger.debug("Socket connect attempt %d failed: %s", attempt + 1, e)
            await asyncio.sleep(delay)

        logger.warning("Could not connect to Dynamic Island socket at %s", self.socket_path)
        return False

    async def _send(self, payload: Dict[str, Any]):
        if not self.is_connected or not self.writer:
            return
        try:
            line = json.dumps(payload) + "\n"
            self.writer.write(line.encode("utf-8"))
            await self.writer.drain()
        except Exception as e:
            logger.error("Failed to send message to Dynamic Island: %s", e)
            self.is_connected = False

    async def set_state(self, state: str):
        """Updates island state: idle, listening, thinking, speaking, executing, error"""
        await self._send({"action": "set_state", "state": state})

    async def set_status(self, text: str):
        """Updates status text shown in the island"""
        await self._send({"action": "set_status", "text": text})

    async def set_transcript(self, text: str):
        """Updates live speech transcript or response"""
        await self._send({"action": "set_transcript", "text": text})

    async def expand(self):
        await self._send({"action": "expand"})

    async def collapse(self):
        await self._send({"action": "collapse"})

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.event_callbacks.append(callback)

    async def _listen_events(self):
        while self.is_connected and self.reader:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                event = json.loads(line.decode("utf-8").strip())
                for cb in self.event_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            asyncio.create_task(cb(event))
                        else:
                            res = cb(event)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                    except Exception as e:
                        logger.error("Error in event callback: %s", e)
            except Exception as e:
                logger.debug("IPC event loop terminated: %s", e)
                break
        self.is_connected = False

    async def close(self):
        self.is_connected = False
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


notch_bridge = NotchBridge()
