"""
Sophia CLI & Daemon Entry Point
Provides CLI commands for running the agent, autonomous self-tests, recursive self-healing,
GCP bootstrapping, and manual triggers.
"""

import argparse
import asyncio
import logging
import sys
from rich.console import Console
from rich.table import Table

from sophia.audio.wake_word import wake_listener
from sophia.core.agent import sophia_agent
from sophia.core.gcp_bootstrap import GCPBootstrapper
from sophia.testing.self_healer import self_healer
from sophia.testing.self_tester import self_tester
from sophia.ui.notch_bridge import notch_bridge

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SophiaCLI")


async def run_tests(heal: bool = False):
    """Runs automated subsystem verification."""
    console.print("\n[bold cyan]=== SOPHIA Autonomous Subsystem Verification ===[/bold cyan]\n")

    if heal:
        result = await self_healer.auto_heal()
        report = result["report"]
    else:
        report = await self_tester.run_all()

    table = Table(title="Sophia Subsystem Health Report")
    table.add_column("Subsystem", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Duration", justify="right")
    table.add_column("Diagnostics", style="dim")

    for res in report["results"]:
        status_str = "[green]PASS[/green]" if res["success"] else "[red]FAIL[/red]"
        table.add_row(res["name"], status_str, f"{res['duration_ms']}ms", res["details"])

    console.print(table)
    if report["all_passed"]:
        console.print("\n[bold green]✓ All subsystems operational.[/bold green]\n")
    else:
        console.print("\n[bold red]✗ Issues detected in some subsystems.[/bold red]\n")


async def run_gcp_bootstrap(project_id: str, project_number: str | None = None):
    """Bootstraps Google Cloud project, billing verification, APIs, and credentials."""
    console.print(f"\n[bold cyan]=== Bootstrapping Google Cloud for Project: {project_id} ===[/bold cyan]\n")
    bootstrapper = GCPBootstrapper(project_id)

    # 1. Set Project
    if not bootstrapper.set_project(project_id):
        console.print(f"[red]Error: Could not switch to project {project_id}[/red]")
        return

    # 2. Check Billing
    billing_info = bootstrapper.verify_billing()
    if billing_info.get("enabled"):
        console.print(f"[green]✓ Billing is ENABLED on project {project_id} (Account: {billing_info.get('billingAccountName')})[/green]")
    else:
        console.print(f"[yellow]! Warning: Billing status check reported: {billing_info.get('error')}[/yellow]")

    # 3. Enable Required APIs
    console.print("[cyan]Enabling Vertex AI, Speech, Vision, and IAM APIs...[/cyan]")
    if bootstrapper.enable_apis():
        console.print("[green]✓ APIs successfully enabled.[/green]")
    else:
        console.print("[yellow]! Some APIs may take a moment to propagate.[/yellow]")

    # 4. Service Account & Credentials
    console.print("[cyan]Setting up Sophia service account and credentials...[/cyan]")
    cred_file = bootstrapper.ensure_service_account()
    if cred_file:
        console.print(f"[green]✓ Service account credentials stored: {cred_file}[/green]")
    else:
        console.print("[yellow]! Service account creation encountered a notice, continuing...[/yellow]")

    # 5. Test Live Gemini Connection
    console.print("[cyan]Testing Gemini Live Intelligence connection...[/cyan]")
    if bootstrapper.test_gemini_connection():
        console.print("[bold green]✓ Gemini connection verified! Sophia is online.[/bold green]\n")
    else:
        console.print("[yellow]! Could not complete test generation (check API keys/quotas).[/yellow]\n")


async def start_daemon():
    """Starts Sophia daemon with Dynamic Island and wake-word listener."""
    console.print("\n[bold magenta]==========================================[/bold magenta]")
    console.print("[bold magenta]        SARAH AI ASSISTANT ONLINE         [/bold magenta]")
    console.print("[bold magenta]==========================================[/bold magenta]\n")
    console.print("[cyan]Dynamic Island floating notch UI is active.[/cyan]")
    console.print("[cyan]Say '[bold white]Sarah[/bold white]' to summon your personal assistant, or click the notch island to expand controls.[/cyan]")
    console.print("[dim]Sarah stays on standby mute until summoned, keeping YouTube, calls, and music 100% free.[/dim]\n")

    await sophia_agent.initialize()

    from sophia.audio.gemini_live import gemini_live_session

    is_mic_muted = False

    async def handle_wake():
        """Handles wake word or manual activation: pauses wake listener and starts Gemini Live."""
        if gemini_live_session.is_running:
            return

        logger.info("Engaging conversational session with Gemini Live (Aoede)...")
        wake_listener.stop()
        try:
            await gemini_live_session.start_session()
        except Exception as e:
            logger.error("Error during live session: %s", e)
        finally:
            await notch_bridge.set_state("idle")
            await notch_bridge.set_status("Ready (Muted)")
            if not is_mic_muted:
                await wake_listener.start(on_wake=handle_wake)

    async def handle_island_event(event: dict):
        """Processes events from Swift Dynamic Island."""
        nonlocal is_mic_muted
        event_type = event.get("event")
        logger.info("Dynamic Island event: %s", event)

        if event_type == "island_toggled":
            is_expanded = event.get("isExpanded", False)
            if is_expanded:
                if not gemini_live_session.is_running:
                    asyncio.create_task(handle_wake())
            else:
                if gemini_live_session.is_running:
                    gemini_live_session.stop()

        elif event_type == "dismiss_clicked":
            if gemini_live_session.is_running:
                gemini_live_session.stop()
            await notch_bridge.set_state("idle")
            await notch_bridge.set_status("Ready (Muted)")

        elif event_type == "mic_toggled":
            is_mic_muted = event.get("isMuted", False)
            if is_mic_muted:
                wake_listener.stop()
                if gemini_live_session.is_running:
                    gemini_live_session.stop()
                await notch_bridge.set_status("Mic Muted")
                logger.info("Microphone muted by user via Dynamic Island.")
            else:
                await wake_listener.start(on_wake=handle_wake)
                await notch_bridge.set_status("Ready (Muted)")
                logger.info("Microphone unmuted by user via Dynamic Island.")

        elif event_type == "voice_changed":
            new_voice = event.get("voice", "Aoede")
            logger.info("Voice changed via Dynamic Island: %s", new_voice)
            wake_listener.stop()
            asyncio.create_task(gemini_live_session.switch_voice(new_voice))

        elif event_type == "vision_toggled":
            vision_active = event.get("isActive", True)
            logger.info("Screen vision toggled: %s", vision_active)

    # Connect to Dynamic Island overlay and set initial idle/muted state
    await notch_bridge.connect()
    notch_bridge.register_callback(handle_island_event)
    await notch_bridge.set_state("idle")
    await notch_bridge.set_status("Ready (Muted)")

    # Start wake listener in standby
    await wake_listener.start(on_wake=handle_wake)

    # Keep alive
    while True:
        await asyncio.sleep(3600)


async def execute_command(text: str):
    """Runs a single prompt through Sophia agent."""
    await sophia_agent.initialize()
    reply = await sophia_agent.process_user_input(text)
    console.print(f"\n[bold cyan]Sarah:[/bold cyan] {reply}\n")


def main():
    parser = argparse.ArgumentParser(description="Sophia: Autonomous AI Personal Assistant for macOS")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # test command
    test_p = subparsers.add_parser("test", help="Run automated subsystem self-test")
    test_p.add_argument("--heal", action="store_true", help="Enable recursive self-healing loop")

    # setup-gcp command
    gcp_p = subparsers.add_parser("setup-gcp", help="Bootstrap Google Cloud project and credentials")
    gcp_p.add_argument("--project-id", required=True, help="GCP Project ID")
    gcp_p.add_argument("--project-number", default=None, help="GCP Project Number")

    # start command
    subparsers.add_parser("start", help="Start Sophia background daemon and Dynamic Island")

    # wake command
    subparsers.add_parser("wake", help="Trigger synthetic wake event")

    # command command
    cmd_p = subparsers.add_parser("ask", help="Send a command directly to Sophia")
    cmd_p.add_argument("text", help="Command or query text")

    # live command
    live_p = subparsers.add_parser("live", help="Start full-duplex conversational session with Gemini Live (Aoede Voice)")
    live_p.add_argument("--voice", default="Aoede", help="Voice persona: Aoede (charming), Kore (poised)")

    args = parser.parse_args()

    if args.command == "test":
        asyncio.run(run_tests(heal=args.heal))
    elif args.command == "setup-gcp":
        asyncio.run(run_gcp_bootstrap(args.project_id, args.project_number))
    elif args.command == "start":
        asyncio.run(start_daemon())
    elif args.command == "live":
        from sophia.audio.gemini_live import GeminiLiveSession
        session = GeminiLiveSession(voice_name=args.voice)
        console.print(f"\n[bold magenta]=== Starting Gemini Live Native Audio ({args.voice} Voice) ===[/bold magenta]")
        console.print("[cyan]Speak into your microphone naturally. Say 'exit' or press Ctrl+C to stop.[/cyan]\n")
        asyncio.run(session.start_session())
    elif args.command == "wake":
        asyncio.run(wake_listener.trigger_synthetic_wake())
    elif args.command == "ask":
        asyncio.run(execute_command(args.text))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
