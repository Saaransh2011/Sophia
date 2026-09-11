"""
Wake Word Detection Engine
Monitors microphone for 'Sophia' keyword and triggers the Dynamic Island overlay and acknowledgment.
Supports dual-triggering: physical mic input AND synthetic computer-triggered injection for recursive testing.
"""

import asyncio
import logging
import random
from typing import Callable, Optional

from sophia.audio.sound_effects import sound_effects
from sophia.core.persona import WAKE_ACKNOWLEDGEMENTS
from sophia.ui.notch_bridge import notch_bridge

logger = logging.getLogger("SophiaWakeWord")


class WakeWordListener:
    """Listens for the 'Sophia' wake word and handles activation."""

    def __init__(self):
        self.is_listening = False
        self.callback: Optional[Callable[[], None]] = None
        self._task: Optional[asyncio.Task] = None

    async def trigger_wake(self, source: str = "voice"):
        """
        Activates Sophia:
        1. Plays gentle futuristic chime
        2. Expands Dynamic Island notch to 'listening' state
        3. Vocally acknowledges ('Yes sir?', 'Mmh?', 'Sophia online, sir.')
        4. Calls registered activation callback
        """
        logger.info("Wake word detected! [Source: %s]", source)

        # 1. Expand Dynamic Island
        await notch_bridge.set_state("listening")
        await notch_bridge.set_status("Listening...")

        # 2. Play wake chime
        await sound_effects.play_chime("wake")

        # 3. Vocal acknowledgment
        ack = random.choice(WAKE_ACKNOWLEDGEMENTS)
        await notch_bridge.set_transcript(ack)
        await sound_effects.speak(ack)

        # 4. Trigger action loop
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback()
            else:
                self.callback()

    async def trigger_synthetic_wake(self):
        """Computer-triggered wake event for automated testing and recursive verification."""
        logger.info("Executing synthetic computer-triggered wake...")
        await self.trigger_wake(source="computer_test_loop")

    async def start(self, on_wake: Optional[Callable[[], None]] = None):
        """Starts the wake word background monitoring loop."""
        self.callback = on_wake
        self.is_listening = True
        logger.info("Sophia Wake Word listener activated (monitoring for 'Sophia')...")

    def stop(self):
        self.is_listening = False
        if self._task:
            self._task.cancel()
        logger.info("Sophia Wake Word listener stopped.")


# Singleton instance
wake_listener = WakeWordListener()
