"""Shared CLI UI helpers for consistent rich output."""

import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                markup=True,
                show_path=False,
                show_level=False,
                show_time=False,
            )
        ],
    )


def success(message: str) -> None:
    console.print(f"[bold green]{message}[/bold green]")


def error(message: str) -> None:
    console.print(f"[bold red]{message}[/bold red]", style="red")


def info(message: str) -> None:
    console.print(f"[cyan]{message}[/cyan]")

