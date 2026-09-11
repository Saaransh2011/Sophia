"""
UTM Virtual Machine Executor
Interfaces with /Applications/UTM.app/Contents/MacOS/utmctl to manage background
virtual machines (Kali Linux, Windows, macOS) and run headless guest workloads.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from sophia.config import config

logger = logging.getLogger("SophiaUTMExecutor")


class UTMExecutor:
    """Manages virtual machines via utmctl for isolated background tasks."""

    def __init__(self, utmctl_path: Optional[str] = None):
        self.utmctl_path = utmctl_path or config.utm.utmctlctl_path if hasattr(config.utm, 'utmctlctl_path') else config.utm.utmctl_path
        self.utm_app = Path("/Applications/UTM.app")

    def is_utm_installed(self) -> bool:
        return self.utm_app.exists() and os.path.exists(self.utmctl_path)

    async def run_utmctl(self, args: List[str], timeout: int = 60) -> Dict[str, Any]:
        """Runs utmctl CLI command."""
        if not self.is_utm_installed():
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"UTM is not installed at {self.utm_app}",
            }

        cmd = [self.utmctl_path] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = stdout_b.decode("utf-8", errors="replace").strip()
            stderr = stderr_b.decode("utf-8", errors="replace").strip()

            is_success = proc.returncode == 0 and "-1743" not in stderr
            return {
                "success": is_success,
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"utmctl {' '.join(args)} timed out after {timeout}s",
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    async def list_vms(self) -> List[Dict[str, str]]:
        """Lists registered virtual machines in UTM."""
        res = await self.run_utmctl(["list"])
        vms = []
        if not res["success"] and not res["stdout"]:
            logger.warning("utmctl list failed: %s", res["stderr"])
            return vms

        lines = res["stdout"].splitlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0] != "UUID":
                uuid = parts[0]
                status = parts[1]
                name = " ".join(parts[2:])
                vms.append({"uuid": uuid, "status": status, "name": name})
        return vms

    async def get_vm_status(self, vm_identifier: str) -> Optional[str]:
        """Queries the status (started, stopped, suspended) of a VM."""
        res = await self.run_utmctl(["status", vm_identifier])
        if res["success"]:
            return res["stdout"].strip()
        return None

    async def start_vm(self, vm_identifier: str) -> Dict[str, Any]:
        """Starts a virtual machine in the background."""
        logger.info("Starting UTM Virtual Machine: %s", vm_identifier)
        return await self.run_utmctl(["start", vm_identifier])

    async def stop_vm(self, vm_identifier: str) -> Dict[str, Any]:
        """Gracefully stops a running VM."""
        logger.info("Stopping UTM Virtual Machine: %s", vm_identifier)
        return await self.run_utmctl(["stop", vm_identifier])

    async def suspend_vm(self, vm_identifier: str) -> Dict[str, Any]:
        """Suspends a VM to memory."""
        logger.info("Suspending UTM Virtual Machine: %s", vm_identifier)
        return await self.run_utmctl(["suspend", vm_identifier])

    async def execute_in_guest(
        self, vm_identifier: str, command: str, args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes a command inside the guest VM via UTM guest agent.
        utmctl exec <vm-id> <command> [args...]
        """
        cli_args = ["exec", vm_identifier, command]
        if args:
            cli_args.extend(args)
        logger.info("Running in VM %s: %s %s", vm_identifier, command, args or [])
        return await self.run_utmctl(cli_args, timeout=300)


# Singleton instance
utm_executor = UTMExecutor()
