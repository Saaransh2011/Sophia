"""
Host Mac Executor
Handles direct execution on macOS: zsh commands, root/sudo, AppleScript,
application control, and local background automation (such as headless Blender).
"""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("SophiaHostExecutor")


class HostExecutor:
    """Executes commands and automations natively on macOS."""

    def __init__(self):
        self.shell = os.environ.get("SHELL", "/bin/zsh")

    async def execute_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 120,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Runs a shell command asynchronously on the host Mac."""
        logger.info("Host executing: %s", command)
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                executable=self.shell,
                cwd=cwd,
                env=merged_env,
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                stdout = stdout_data.decode("utf-8", errors="replace")
                stderr = stderr_data.decode("utf-8", errors="replace")
                return {
                    "success": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            except asyncio.TimeoutError:
                proc.kill()
                logger.error("Command timed out after %s seconds: %s", timeout, command)
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout}s",
                }

        except Exception as e:
            logger.exception("Host command execution error: %s", e)
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    async def run_applescript(self, script: str) -> Dict[str, Any]:
        """Executes an AppleScript via osascript for macOS UI/app control."""
        cmd = f"osascript -e '{script}'"
        return await self.execute_command(cmd)

    async def launch_application(self, app_name: str, background: bool = False) -> Dict[str, Any]:
        """Opens or activates a macOS application."""
        bg_flag = "-g" if background else ""
        cmd = f"open {bg_flag} -a \"{app_name}\""
        return await self.execute_command(cmd)

    async def run_blender_script(self, python_code: str, headless: bool = True) -> Dict[str, Any]:
        """
        Executes a Python modeling script in Blender.
        If headless is True, runs with `blender -b -P <script>` in the background
        without interrupting the user's active display.
        """
        blender_path = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
        if not os.path.exists(blender_path):
            return {
                "success": False,
                "error": "Blender application not found. Please install Blender in /Applications.",
            }

        temp_script = Path("/tmp/sophia_blender_task.py")
        temp_script.write_text(python_code, encoding="utf-8")

        flags = "-b" if headless else ""
        cmd = f"\"{blender_path}\" {flags} -P \"{temp_script}\""
        logger.info("Running Blender automation (headless=%s)...", headless)
        return await self.execute_command(cmd, timeout=300)

    async def set_system_volume(self, level_percent: int) -> Dict[str, Any]:
        """Sets macOS system volume (0-100)."""
        vol = max(0, min(100, level_percent))
        script = f"set volume output volume {vol}"
        return await self.run_applescript(script)


# Singleton instance
host_executor = HostExecutor()
