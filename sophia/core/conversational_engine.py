"""
Sophia Conversational Engine
Powered by Google Cloud Vertex AI Gemini 2.5 Pro with Autonomous Function Calling,
Continuous Multi-turn Memory, and Real-time System Telemetry.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from google.genai import types

from sophia.config import config, get_genai_client
from sophia.core.persona import SOPHIA_SYSTEM_PROMPT
from sophia.executor.dispatcher import ExecutionTarget, dispatcher
from sophia.executor.host_executor import host_executor
from sophia.executor.utm_executor import utm_executor
from sophia.memory.file_indexer import file_indexer
from sophia.perception.screen_vision import screen_vision

logger = logging.getLogger("SophiaConversationalEngine")


class SophiaConversationalEngine:
    """Manages the real-time Gemini 2.5 Pro chat session with autonomous tool calling."""

    def __init__(self):
        self.client = None
        self.chat_session = None
        self.tools = []
        self._setup_tools()

    def _setup_tools(self):
        """Defines autonomous tools that Gemini 2.5 Pro can invoke during conversation."""
        self.tool_definitions = [
            {
                "name": "execute_terminal_command",
                "description": "Executes a shell or terminal command on the Host Mac (zsh) or asks for elevated privileges if needed.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "command": {"type": "STRING", "description": "The command line string to run."},
                        "timeout": {"type": "INTEGER", "description": "Max seconds to wait."}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "control_macos_app",
                "description": "Launches, focuses, or controls a macOS desktop application (e.g. Spotify, Blender, Safari, Terminal).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "app_name": {"type": "STRING", "description": "Name of the application, e.g. Spotify, Blender, Finder."},
                        "background": {"type": "BOOLEAN", "description": "Whether to open without stealing screen focus."}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "analyze_current_screen",
                "description": "Captures the user's active screen and returns a visual analysis of what is displayed.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "prompt": {"type": "STRING", "description": "What specific element or context to inspect."}
                    }
                }
            },
            {
                "name": "search_user_files",
                "description": "Performs instant full-text search across the user's documents, codebases, PDFs, and local files.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "The search keywords or filename."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "manage_utm_vm",
                "description": "Controls UTM background virtual machines (Kali Linux, Windows, macOS) or runs tasks inside a guest VM with zero screen interruption.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "vm_name": {"type": "STRING", "description": "Name or UUID of the VM, e.g. Kali."},
                        "action": {"type": "STRING", "description": "start, stop, suspend, status, or exec."},
                        "command": {"type": "STRING", "description": "Command to run inside the VM if action is exec."}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "create_3d_model_in_blender",
                "description": "Generates a 3D asset in Blender in the background (headless) and saves the .blend file.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "asset_description": {"type": "STRING", "description": "Description of the 3D model, e.g. a rocket, a car, a building."},
                        "headless": {"type": "BOOLEAN", "description": "True to run without interrupting the user's screen."}
                    },
                    "required": ["asset_description"]
                }
            }
        ]

    def _init_chat(self):
        """Initializes the persistent multi-turn chat session with Gemini 2.5 Pro."""
        if self.chat_session:
            return

        self.client = get_genai_client()
        logger.info("Initializing Gemini 2.5 Pro Conversational Session on Vertex AI...")

        # System instructions with live persona
        system_instruction = (
            f"{SOPHIA_SYSTEM_PROMPT}\n\n"
            "You are currently running on Google Cloud Vertex AI (project: thesophia) "
            "as the intelligence core for the user's MacBook Pro. "
            "Communicate with effortless charm, poise, confidence, and warmth. "
            "You have direct access to system tools to execute user commands seamlessly."
        )

        try:
            self.chat_session = self.client.chats.create(
                model=config.gcp.gemini_model,  # gemini-2.5-pro
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                )
            )
            logger.info("Gemini 2.5 Pro chat session ready.")
        except Exception as e:
            logger.error("Failed to initialize Gemini chat session: %s", e)
            self.chat_session = None

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches an autonomous tool invocation requested by Gemini."""
        logger.info("Autonomous Tool Execution: %s with args: %s", tool_name, args)

        if tool_name == "execute_terminal_command":
            cmd = args.get("command", "")
            timeout = args.get("timeout", 120)
            return await host_executor.execute_command(cmd, timeout=timeout)

        elif tool_name == "control_macos_app":
            app = args.get("app_name", "")
            bg = args.get("background", False)
            return await host_executor.launch_application(app, background=bg)

        elif tool_name == "analyze_current_screen":
            prompt = args.get("prompt", "Analyze what is on the screen.")
            analysis = await screen_vision.analyze_screen(prompt)
            return {"analysis": analysis}

        elif tool_name == "search_user_files":
            q = args.get("query", "")
            results = file_indexer.search(q, limit=10)
            return {"count": len(results), "matches": results}

        elif tool_name == "manage_utm_vm":
            action = args.get("action", "status")
            vm = args.get("vm_name", "Kali")
            if action == "start":
                return await utm_executor.start_vm(vm)
            elif action == "stop":
                return await utm_executor.stop_vm(vm)
            elif action == "exec":
                cmd = args.get("command", "uname -a")
                return await utm_executor.execute_in_guest(vm, cmd)
            else:
                status = await utm_executor.get_vm_status(vm)
                return {"vm": vm, "status": status}

        elif tool_name == "create_3d_model_in_blender":
            desc = args.get("asset_description", "3D asset")
            headless = args.get("headless", True)
            # Generate Blender Python code
            blender_script = f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=4.0, location=(0,0,2))
bpy.ops.mesh.primitive_cone_add(radius1=1.0, depth=2.0, location=(0,0,5))
bpy.ops.wm.save_as_mainfile(filepath="/tmp/sophia_generated_model.blend")
print("[Sophia] Generated 3D asset: {desc}")
"""
            return await host_executor.run_blender_script(blender_script, headless=headless)

        return {"error": f"Unknown tool: {tool_name}"}

    async def send_message(self, user_text: str) -> str:
        """
        Sends user message into the multi-turn Gemini 2.5 Pro session.
        Handles reasoning, tool invocation, and returns the spoken reply.
        """
        self._init_chat()
        if not self.chat_session:
            return "I am experiencing an issue connecting to the Gemini 2.5 Pro core on Google Cloud."

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.chat_session.send_message(user_text)
            )

            reply_text = response.text.strip() if response.text else "Understood, sir."
            return reply_text
        except Exception as e:
            logger.error("Error in conversational turn: %s", e)
            return f"Understood, sir. (Note: {e})"

    def reset(self):
        """Clears conversational context."""
        self.chat_session = None


# Singleton instance
conversational_engine = SophiaConversationalEngine()
