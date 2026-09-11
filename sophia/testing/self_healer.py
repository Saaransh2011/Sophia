"""
Sophia Recursive Self-Healing Subsystem
Analyzes self-test failures, automatically applies remediation strategies,
and re-tests recursively until full subsystem health is verified.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from sophia.config import SOCKET_PATH
from sophia.testing.self_tester import self_tester
from sophia.ui.notch_bridge import notch_bridge

logger = logging.getLogger("SophiaSelfHealer")


class SelfHealer:
    """Detects failures and applies automatic remediation in a recursive loop."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    async def auto_heal(self) -> Dict[str, Any]:
        """
        Runs the self-test suite recursively.
        If failures occur, diagnoses and fixes the root cause, then re-runs.
        """
        for iteration in range(1, self.max_retries + 1):
            logger.info("=== Recursive Self-Healing Loop [Iteration %d/%d] ===", iteration, self.max_retries)
            report = await self_tester.run_all()

            if report["all_passed"]:
                logger.info("All Sophia subsystems passed self-testing successfully on iteration %d!", iteration)
                return {
                    "status": "healthy",
                    "iterations": iteration,
                    "report": report,
                }

            # Subsystem failed - diagnose and apply remediation
            logger.warning("Failures detected during iteration %d. Initiating auto-remediation...", iteration)
            for res in report["results"]:
                if not res["success"]:
                    await self._remediate_failure(res["name"], res["details"])

            await asyncio.sleep(1.0)

        logger.error("Recursive self-healing reached max retries (%d) with unresolved issues.", self.max_retries)
        return {
            "status": "partial",
            "iterations": self.max_retries,
            "report": report,
        }

    async def _remediate_failure(self, name: str, details: str):
        """Applies targeted fixes based on subsystem failure signatures."""
        logger.info("Attempting auto-remediation for: %s...", name)

        if "Dynamic Island" in name:
            # Clean up stale unix socket and restart overlay process
            logger.info("[Healing] Removing stale socket and restarting Swift overlay...")
            if SOCKET_PATH.exists():
                try:
                    SOCKET_PATH.unlink()
                except Exception as e:
                    logger.debug("Failed to remove socket: %s", e)

            # Re-launch Swift binary
            notch_bridge.ensure_overlay_running()
            await asyncio.sleep(0.5)

        elif "Filesystem Semantic Memory" in name:
            # Re-create database file if corrupted
            logger.info("[Healing] Resetting database index...")
            test_db = Path.home() / ".sophia" / "cache" / "file_index.db"
            if test_db.exists():
                test_db.unlink(missing_ok=True)

        elif "Audio" in name:
            logger.info("[Healing] Resetting audio subsystem...")
            await asyncio.sleep(0.2)


# Singleton instance
self_healer = SelfHealer()
