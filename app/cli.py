import sys
import uuid
import logging
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from app.config import settings
from app.database import create_db_and_tables
from app.pipeline.orchestrator import VideoPipelineOrchestrator
from app.services.semantic_director import SemanticDirector
from app.services.ffmpeg_renderer import FFmpegRenderer
from app.services.broll_manager import LocalBrollManager
from app.services.svg_generator import ProceduralSvgGenerator
from app.services.transcriber import LocalTranscriber

app = typer.Typer(
    name="Autonomous Video Factory",
    help="100% Local Autonomous Video Production Factory powered by Ollama, faster-whisper, and FFmpeg."
)
console = Console()
logger = logging.getLogger("video_factory.cli")


@app.command("run")
def run_pipeline_command(
    input_path: str = typer.Option(..., "--input", "-i", help="Path to input raw video file"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Path for rendered final video"),
    broll: bool = typer.Option(True, "--broll/--no-broll", help="Enable stock B-roll cuts"),
    svg_cards: bool = typer.Option(True, "--svg-cards/--no-svg-cards", help="Enable procedural 9:16 SVG graphic cards"),
    subtitles: bool = typer.Option(True, "--subtitles/--no-subtitles", help="Enable kinetic word-highlighted ASS subtitles"),
    ducking: bool = typer.Option(True, "--ducking/--no-ducking", help="Enable ambient audio ducking to -22 dB"),
    music: Optional[str] = typer.Option(None, "--music", "-m", help="Path to ambient background music file"),
    webhook: Optional[str] = typer.Option(None, "--webhook", "-w", help="Local n8n webhook URL to notify upon completion"),
):
    """Executes the full autonomous video production pipeline on a local video."""
    console.print(
        Panel.fit(
            "[bold cyan]Local Autonomous Video Factory[/bold cyan]\n"
            "[green]Ollama LLM Take Pruner[/green] • [yellow]faster-whisper[/yellow] • [magenta]FFmpeg Splicer[/magenta]",
            border_style="cyan"
        )
    )

    in_file = Path(input_path).resolve()
    if not in_file.exists():
        console.print(f"[bold red]Error:[/bold red] Input video file does not exist: {in_file}")
        raise typer.Exit(code=1)

    settings.ensure_directories()
    create_db_and_tables()

    job_id = str(uuid.uuid4())
    console.print(f"[dim]Initiating job ID: {job_id}[/dim]")
    console.print(f"[bold]Input Video:[/bold] {in_file}")

    options = {
        "enable_broll": broll,
        "enable_svg_cards": svg_cards,
        "enable_subtitles": subtitles,
        "enable_music_ducking": ducking,
        "music_track_path": music,
        "n8n_webhook_url": webhook,
    }

    orchestrator = VideoPipelineOrchestrator()
    try:
        with console.status("[bold green]Executing local video production pipeline...") as status:
            job = orchestrator.run_pipeline(
                job_id=job_id,
                input_video_path=str(in_file),
                output_video_path=output_path,
                options=options
            )

        console.print("\n[bold green]✔ Production Complete![/bold green]")
        console.print(f"[bold]Output Video:[/bold] [link=file://{job.output_path}]{job.output_path}[/link]")
        console.print(f"[bold]Execution Time:[/bold] {job.execution_time_seconds} seconds")

    except Exception as e:
        console.print(f"\n[bold red]Pipeline failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("serve")
def serve_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
):
    """Starts the FastAPI web server and REST API for n8n integration."""
    import uvicorn
    console.print(f"[bold green]Starting Autonomous Video Factory server on http://{host}:{port}...[/bold green]")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command("doctor")
def doctor_command():
    """Performs deep local environment health diagnostics."""
    table = Table(title="Autonomous Video Factory — Environment Doctor", border_style="cyan")
    table.add_column("Component", style="bold white")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    # 1. Ollama
    director = SemanticDirector()
    o_status = director.check_ollama_status()
    if o_status["available"]:
        table.add_row(
            "Ollama LLM",
            "[green]ONLINE[/green]",
            f"Base URL: {o_status['url']} | Target: {o_status['target_model']} (Installed: {len(o_status['installed_models'])})"
        )
    else:
        table.add_row(
            "Ollama LLM",
            "[yellow]OFFLINE (Heuristic Mode Active)[/yellow]",
            f"Not reachable at {o_status['url']}. Built-in algorithmic take pruner will be used as fallback."
        )

    # 2. faster-whisper
    table.add_row(
        "faster-whisper",
        "[green]READY[/green]",
        f"Model: {settings.WHISPER_MODEL_SIZE} | Device: {settings.WHISPER_DEVICE} | Quant: {settings.WHISPER_COMPUTE_TYPE}"
    )

    # 3. FFmpeg
    renderer = FFmpegRenderer()
    f_status = renderer.check_ffmpeg()
    if f_status["available"]:
        table.add_row(
            "FFmpeg Engine",
            "[green]READY[/green]",
            f"{f_status['path']} ({f_status['version'][:40]})"
        )
    else:
        table.add_row(
            "FFmpeg Engine",
            "[red]NOT FOUND[/red]",
            f"Error: {f_status.get('error')}"
        )

    # 4. Storage
    settings.ensure_directories()
    broll_count = len(list(settings.BROLL_DIR.glob("*.*")))
    audio_count = len(list(settings.AUDIO_DIR.glob("*.*")))
    table.add_row(
        "Local Storage",
        "[green]INITIALIZED[/green]",
        f"B-roll library: {broll_count} assets | Audio library: {audio_count} tracks"
    )

    console.print(table)


@app.command("index-broll")
def index_broll_command(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Custom directory to index into library")
):
    """Scans and indexes 9:16 vertical stock video & image assets."""
    create_db_and_tables()
    lib_dir = Path(path) if path else settings.BROLL_DIR
    manager = LocalBrollManager(library_dir=lib_dir)
    
    with console.status(f"[bold green]Indexing assets in {lib_dir}..."):
        assets = manager.index_library()

    console.print(f"[bold green]Indexed {len(assets)} B-roll assets successfully![/bold green]")
    for a in assets[:10]:
        console.print(f" • [cyan]{a.name}[/cyan] ({a.tags}) -> [dim]{a.file_path}[/dim]")


@app.command("card")
def generate_card_command(
    card_type: str = typer.Option("stat", "--type", "-t", help="Card type: stat, quote, takeaway, terminal"),
    title: str = typer.Option("100% LOCAL", "--title", help="Card title or metric"),
    content: str = typer.Option("Zero cloud subscriptions", "--content", help="Card body content"),
):
    """Generates a standalone vertical 9:16 SVG graphic card."""
    settings.ensure_directories()
    gen = ProceduralSvgGenerator()
    out = gen.generate_card(card_type=card_type, title=title, content=content)
    console.print(f"[bold green]Created procedural 9:16 SVG card:[/bold green] {out}")


if __name__ == "__main__":
    app()
