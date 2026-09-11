"""
Sophia Dual-World Dispatcher
Intelligently routes tasks to either the Host Mac or an Isolated Background UTM Virtual Machine.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

from sophia.executor.host_executor import host_executor
from sophia.executor.utm_executor import utm_executor

logger = logging.getLogger("SophiaDispatcher")


class ExecutionTarget(str, Enum):
    HOST = "host"
    UTM_VM = "utm_vm"
    AUTO = "auto"


class TaskDispatcher:
    """Classifies and dispatches commands between Host Mac and UTM Virtual Machines."""

    def __init__(self):
        self.host = host_executor
        self.utm = utm_executor

    def determine_target(self, task_description: str) -> ExecutionTarget:
        """Heuristic and intent-based routing between Host and VM."""
        lower = task_description.lower()

        # Keywords indicating VM execution
        vm_keywords = [
            "vm", "virtual machine", "kali", "linux", "exploit", "hack", "penetration",
            "isolate", "sandbox", "background compile", "long running job"
        ]
        if any(kw in lower for kw in vm_keywords):
            return ExecutionTarget.UTM_VM

        # Keywords indicating Host Mac execution
        host_keywords = [
            "open", "launch", "volume", "music", "spotify", "safari", "screen",
            "finder", "screenshot", "active window", "click", "keyboard", "say"
        ]
        if any(kw in lower for kw in host_keywords):
            return ExecutionTarget.HOST

        # Default to Host with background execution flag if not specified
        return ExecutionTarget.HOST

    async def dispatch(
        self,
        task_type: str,
        params: Dict[str, Any],
        target: ExecutionTarget = ExecutionTarget.AUTO,
    ) -> Dict[str, Any]:
        """
        Executes a task on the appropriate execution target.
        """
        selected_target = target
        if selected_target == ExecutionTarget.AUTO:
            selected_target = self.determine_target(params.get("description", task_type))

        logger.info("Dispatching task '%s' to target: %s", task_type, selected_target.value)

        if selected_target == ExecutionTarget.UTM_VM:
            vm_name = params.get("vm_name", "Kali")
            command = params.get("command", "")
            args = params.get("args", [])
            return await self.utm.execute_in_guest(vm_name, command, args)

        # Host Execution
        if task_type == "shell":
            return await self.host.execute_command(
                params.get("command", ""),
                cwd=params.get("cwd"),
                timeout=params.get("timeout", 120),
            )
        elif task_type == "applescript":
            return await self.host.run_applescript(params.get("script", ""))
        elif task_type == "launch_app":
            return await self.host.launch_application(
                params.get("app_name", ""),
                background=params.get("background", False),
            )
        elif task_type == "blender":
            return await self.host.run_blender_script(
                params.get("script", ""),
                headless=params.get("headless", True),
            )
        elif task_type == "volume":
            return await self.host.set_system_volume(params.get("level", 50))
        else:
            return {
                "success": False,
                "error": f"Unknown task type: {task_type}",
            }


# Singleton instance
dispatcher = TaskDispatcher()
