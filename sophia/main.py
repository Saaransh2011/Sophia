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
    console.print("[bold magenta]       SOPHIA AI ASSISTANT ONLINE         [/bold magenta]")
    console.print("[bold magenta]==========================================[/bold magenta]\n")
    console.print("[cyan]Dynamic Island floating notch UI is active.[/cyan]")
    console.print("[cyan]Say '[bold white]Sophia[/bold white]' to summon your personal assistant, or trigger commands via terminal.[/cyan]\n")

    await sophia_agent.initialize()
    await wake_listener.start(on_wake=lambda: asyncio.create_task(notch_bridge.set_state("listening")))

    # Keep alive
    while True:
        await asyncio.sleep(3600)


async def execute_command(text: str):
    """Runs a single prompt through Sophia agent."""
    await sophia_agent.initialize()
    reply = await sophia_agent.process_user_input(text)
    console.print(f"\n[bold cyan]Sophia:[/bold cyan] {reply}\n")


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
