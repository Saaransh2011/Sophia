"""
Sophia Central Autonomous Agent
Orchestrates perception, intent understanding, tool execution, dual-world routing,
and dynamic island presentation.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sophia.config import config
from sophia.core.persona import SOPHIA_SYSTEM_PROMPT
from sophia.executor.dispatcher import ExecutionTarget, dispatcher
from sophia.executor.host_executor import host_executor
from sophia.executor.utm_executor import utm_executor
from sophia.memory.file_indexer import file_indexer
from sophia.perception.camera_vision import camera_vision
from sophia.perception.screen_vision import screen_vision
from sophia.ui.notch_bridge import notch_bridge

logger = logging.getLogger("SophiaAgent")


class SophiaAgent:
    """The central intelligence orchestrating Sophia's capabilities."""

    def __init__(self):
        self.system_prompt = SOPHIA_SYSTEM_PROMPT
        self.conversation_history: List[Dict[str, str]] = []

    async def initialize(self):
        """Initializes UI bridge and starts file indexer."""
        logger.info("Initializing Sophia Agent subsystems...")
        # Connect to Dynamic Island overlay
        await notch_bridge.connect()
        await notch_bridge.set_state("idle")

    async def process_user_input(self, user_text: str) -> str:
        """
        Processes a natural language command from the user:
        1. Updates Dynamic Island to 'thinking'
        2. Gathers context (active app, files if relevant)
        3. Decides action (host, VM, vision, or direct response)
        4. Executes and reports back to Dynamic Island
        """
        logger.info("Processing command: '%s'", user_text)
        await notch_bridge.set_state("thinking")
        await notch_bridge.set_status(f"Processing: {user_text[:25]}...")

        # Analyze intent and check for specialized actions
        lower = user_text.lower()

        # 1. Screen Vision Query
        if any(w in lower for w in ["what's on my screen", "look at my screen", "see screen", "screen summary"]):
            await notch_bridge.set_status("Analyzing screen...")
            analysis = await screen_vision.analyze_screen(user_text)
            await self._respond(analysis)
            return analysis

        # 2. Camera / Object / Emotion Query
        if any(w in lower for w in ["look at me", "what am i holding", "what object", "my emotion", "look through camera"]):
            await notch_bridge.set_status("Analyzing camera feed...")
            res = await camera_vision.identify_objects_or_emotion(user_text)
            await self._respond(res)
            return res

        # 3. File search query
        if any(w in lower for w in ["find file", "search file", "where is the file", "look for document"]):
            query = user_text.replace("find file", "").replace("search file", "").strip()
            files = file_indexer.search(query, limit=5)
            if files:
                reply = f"Found {len(files)} matches:\n" + "\n".join([f"- {f['filename']} ({f['path']})" for f in files])
            else:
                reply = f"No local files found matching '{query}'."
            await self._respond(reply)
            return reply

        # 4. Blender 3D Model request
        if "blender" in lower and any(w in lower for w in ["rocket", "model", "render", "create 3d"]):
            await notch_bridge.set_state("executing")
            await notch_bridge.set_status("Generating 3D model in background...")

            # Python code to generate a 3D rocket in Blender headlessly
            blender_script = """
import bpy

# Clear existing objects
bpy.ops.wm.read_factory_settings(use_empty=True)

# Create Rocket Body (Cylinder)
bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=4.0, location=(0, 0, 2))
body = bpy.context.active_object
body.name = "RocketBody"

# Create Rocket Nose Cone (Cone)
bpy.ops.mesh.primitive_cone_add(radius1=1.0, depth=2.0, location=(0, 0, 5))
cone = bpy.context.active_object
cone.name = "RocketNoseCone"

# Create 4 Fins
for i, angle in enumerate([0, 90, 180, 270]):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.2, 0, 0.5))
    fin = bpy.context.active_object
    fin.scale = (0.2, 0.8, 1.2)
    bpy.ops.object.transform_apply(scale=True)
    fin.rotation_euler = (0, 0, angle * 3.14159 / 180)
    fin.name = f"Fin_{i+1}"

# Save file
output_path = "/tmp/sophia_rocket.blend"
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"[Sophia] Rocket model successfully built and saved to {output_path}")
"""
            # Run in headless background without interrupting the user's screen
            result = await dispatcher.dispatch("blender", {
                "description": "Background 3D Rocket Generation",
                "script": blender_script,
                "headless": True,
            })

            if result.get("success"):
                reply = "I have created the 3D rocket model in Blender in the background. It is saved and ready for you, sir."
            else:
                reply = f"Blender background task reported: {result.get('error') or result.get('stderr')}"

            await self._respond(reply)
            return reply

        # 5. Dual-World Routing for General Tasks
        target = dispatcher.determine_target(user_text)
        if target == ExecutionTarget.UTM_VM:
            await notch_bridge.set_state("executing")
            await notch_bridge.set_status("Routing to Background VM...")
            res = await dispatcher.dispatch("vm_task", {"description": user_text}, target=target)
            reply = f"Background VM task executed: {res.get('stdout') or res.get('stderr')}"
            await self._respond(reply)
            return reply

        # 6. Fallback: Conversational response using Gemini
        reply = await self._generate_gemini_reply(user_text)
        await self._respond(reply)
        return reply

    async def _generate_gemini_reply(self, user_prompt: str) -> str:
        """Generates conversational response using Gemini."""
        try:
            from google import genai
            client = genai.Client()
            response = client.models.generate_content(
                model=config.gcp.gemini_model,
                contents=[
                    f"System: {self.system_prompt}",
                    f"User: {user_prompt}",
                ]
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Gemini generation failed: %s", e)
            return f"Yes sir. I am currently operating locally. (GCP response note: {e})"

    async def _respond(self, reply_text: str):
        """Displays response in Dynamic Island and delivers vocal speech."""
        logger.info("Sophia replying: %s", reply_text)
        await notch_bridge.set_state("speaking")
        await notch_bridge.set_status(reply_text[:40] + ("..." if len(reply_text) > 40 else ""))
        await notch_bridge.set_transcript(reply_text)

        # Vocal playback
        from sophia.audio.sound_effects import sound_effects
        await sound_effects.speak(reply_text)

        # After speaking, settle back to idle
        await asyncio.sleep(2.0)
        await notch_bridge.set_state("idle")


# Singleton instance
sophia_agent = SophiaAgent()
