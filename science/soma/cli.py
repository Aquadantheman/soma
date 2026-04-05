"""
Soma CLI Dashboard
------------------
Rich terminal interface for viewing your biosignal baselines and recent data.

Usage:
    python -m soma.cli status
    python -m soma.cli baselines
    python -m soma.cli signals hrv_rmssd --days 7
    python -m soma.cli check hrv_rmssd 28.5
"""

import sys
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from sqlalchemy import create_engine, text
import os

from .baseline.model import compute_baseline, compute_deviation, BiomarkerBaseline

console = Console()

DATABASE_URL = os.environ.get(
    "SOMA_DATABASE_URL",
    "postgresql://postgres:soma_dev@127.0.0.1:5432/soma"
)


def get_engine():
    return create_engine(DATABASE_URL)


def cmd_status():
    """Show system status and data coverage."""
    engine = get_engine()

    with engine.connect() as conn:
        # Total signals
        total = conn.execute(text("SELECT COUNT(*) FROM signals")).scalar() or 0

        # Date range
        range_result = conn.execute(
            text("SELECT MIN(time), MAX(time) FROM signals")
        ).first()

        # Biomarker coverage
        coverage = conn.execute(text("""
            SELECT
                s.biomarker_slug,
                bt.name,
                bt.category,
                COUNT(*) as count,
                MIN(s.time) as earliest,
                MAX(s.time) as latest
            FROM signals s
            JOIN biomarker_types bt ON s.biomarker_slug = bt.slug
            GROUP BY s.biomarker_slug, bt.name, bt.category
            ORDER BY count DESC
        """)).fetchall()

        # Baselines computed
        baselines = conn.execute(text("""
            SELECT DISTINCT ON (biomarker_slug)
                biomarker_slug, computed_at, sample_count, mean, std_dev
            FROM baselines
            ORDER BY biomarker_slug, computed_at DESC
        """)).fetchall()

    # Header panel
    if range_result and range_result[0]:
        date_info = f"Data from {range_result[0]:%Y-%m-%d} to {range_result[1]:%Y-%m-%d}"
    else:
        date_info = "No data yet"

    console.print(Panel(
        f"[bold cyan]Soma[/] - Personal Biosignal Baseline\n\n"
        f"[dim]{date_info}[/]\n"
        f"Total signals: [bold]{total:,}[/]",
        title="Status",
        border_style="cyan",
    ))

    # Coverage table
    if coverage:
        table = Table(title="Biomarker Coverage", box=box.ROUNDED)
        table.add_column("Biomarker", style="cyan")
        table.add_column("Category", style="dim")
        table.add_column("Signals", justify="right")
        table.add_column("Date Range", style="dim")

        for row in coverage:
            date_range = f"{row[4]:%m/%d} - {row[5]:%m/%d}" if row[4] else "-"
            table.add_row(row[1], row[2], f"{row[3]:,}", date_range)

        console.print(table)

    # Baselines table
    if baselines:
        console.print()
        table = Table(title="Computed Baselines", box=box.ROUNDED)
        table.add_column("Biomarker", style="cyan")
        table.add_column("Mean", justify="right")
        table.add_column("Std Dev", justify="right")
        table.add_column("Samples", justify="right")
        table.add_column("Computed", style="dim")

        for row in baselines:
            table.add_row(
                row[0],
                f"{row[3]:.2f}" if row[3] else "-",
                f"{row[4]:.2f}" if row[4] else "-",
                str(row[2]) if row[2] else "-",
                f"{row[1]:%Y-%m-%d}" if row[1] else "-",
            )

        console.print(table)
    else:
        console.print("\n[dim]No baselines computed yet. Run: POST /baselines/compute[/]")


def cmd_baselines():
    """Show all computed baselines with detailed statistics."""
    engine = get_engine()

    with engine.connect() as conn:
        baselines = conn.execute(text("""
            SELECT DISTINCT ON (biomarker_slug)
                b.biomarker_slug,
                bt.name,
                bt.unit,
                b.mean,
                b.std_dev,
                b.p10, b.p25, b.p50, b.p75, b.p90,
                b.sample_count,
                b.window_days,
                b.computed_at
            FROM baselines b
            JOIN biomarker_types bt ON b.biomarker_slug = bt.slug
            ORDER BY biomarker_slug, computed_at DESC
        """)).fetchall()

    if not baselines:
        console.print("[yellow]No baselines computed yet.[/]")
        console.print("Run the API endpoint: POST /baselines/compute")
        return

    for row in baselines:
        slug, name, unit, mean, std, p10, p25, p50, p75, p90, n, window, computed = row

        # Create distribution visualization
        cv = (std / mean * 100) if mean and std else 0
        stability = "[green]stable[/]" if cv < 30 else "[yellow]variable[/]"

        panel_content = (
            f"[bold]Mean:[/] {mean:.2f} {unit}  [dim]|[/]  "
            f"[bold]Std:[/] {std:.2f}  [dim]|[/]  "
            f"CV: {cv:.1f}% ({stability})\n\n"
            f"[dim]Percentiles:[/]\n"
            f"  p10: {p10:.2f}  p25: {p25:.2f}  [bold]p50: {p50:.2f}[/]  "
            f"p75: {p75:.2f}  p90: {p90:.2f}\n\n"
            f"[dim]Based on {n} samples over {window} days (computed {computed:%Y-%m-%d})[/]"
        )

        console.print(Panel(
            panel_content,
            title=f"[cyan]{name}[/] ({slug})",
            border_style="blue",
        ))
        console.print()


def cmd_signals(biomarker_slug: str, days: int = 7):
    """Show recent signals for a biomarker."""
    engine = get_engine()
    cutoff = datetime.now() - timedelta(days=days)

    with engine.connect() as conn:
        # Get biomarker info
        bio = conn.execute(
            text("SELECT name, unit FROM biomarker_types WHERE slug = :slug"),
            {"slug": biomarker_slug}
        ).first()

        if not bio:
            console.print(f"[red]Unknown biomarker: {biomarker_slug}[/]")
            return

        signals = conn.execute(text("""
            SELECT time, value, source_slug, quality
            FROM signals
            WHERE biomarker_slug = :slug AND time >= :cutoff
            ORDER BY time DESC
            LIMIT 50
        """), {"slug": biomarker_slug, "cutoff": cutoff}).fetchall()

    if not signals:
        console.print(f"[yellow]No signals found for {biomarker_slug} in last {days} days[/]")
        return

    table = Table(title=f"{bio[0]} - Last {days} Days", box=box.ROUNDED)
    table.add_column("Time", style="dim")
    table.add_column("Value", justify="right", style="cyan")
    table.add_column("Unit", style="dim")
    table.add_column("Source", style="dim")

    for row in signals:
        table.add_row(
            f"{row[0]:%Y-%m-%d %H:%M}",
            f"{row[1]:.2f}" if row[1] else "-",
            bio[1],
            row[2],
        )

    console.print(table)


def cmd_check(biomarker_slug: str, value: float):
    """Check how a value compares to your personal baseline."""
    engine = get_engine()

    with engine.connect() as conn:
        # Get baseline
        baseline_row = conn.execute(text("""
            SELECT
                b.biomarker_slug, b.mean, b.std_dev as std,
                b.p10, b.p25, b.p50 as median, b.p75, b.p90,
                b.sample_count, b.window_days, b.computed_at,
                bt.name, bt.unit
            FROM baselines b
            JOIN biomarker_types bt ON b.biomarker_slug = bt.slug
            WHERE b.biomarker_slug = :slug
            ORDER BY computed_at DESC
            LIMIT 1
        """), {"slug": biomarker_slug}).first()

    if not baseline_row:
        console.print(f"[red]No baseline found for {biomarker_slug}[/]")
        console.print("Compute baselines first: POST /baselines/compute")
        return

    # Build baseline object
    baseline = BiomarkerBaseline(
        biomarker_slug=baseline_row[0],
        computed_at=pd.Timestamp(baseline_row[10]),
        window_days=baseline_row[9],
        mean=baseline_row[1],
        std=baseline_row[2],
        median=baseline_row[5],
        p10=baseline_row[3],
        p25=baseline_row[4],
        p75=baseline_row[6],
        p90=baseline_row[7],
        sample_count=baseline_row[8],
        is_stable=True,
        coefficient_of_variation=baseline_row[2] / baseline_row[1] if baseline_row[1] else 0,
    )

    deviation = compute_deviation(value, baseline)

    # Determine color based on significance
    if deviation.is_significant:
        color = "red" if deviation.direction == "below" else "yellow"
        level = "SIGNIFICANT"
    elif deviation.is_notable:
        color = "yellow"
        level = "Notable"
    else:
        color = "green"
        level = "Normal"

    # Direction indicator (ASCII-compatible)
    if deviation.z_score > 0.5:
        arrow = "[bold red]^[/]"
    elif deviation.z_score < -0.5:
        arrow = "[bold blue]v[/]"
    else:
        arrow = "[dim]-[/]"

    console.print(Panel(
        f"[bold]{baseline_row[11]}[/] ({biomarker_slug})\n\n"
        f"Observed: [bold cyan]{value:.2f}[/] {baseline_row[12]} {arrow}\n"
        f"Baseline: {baseline.mean:.2f} ± {baseline.std:.2f}\n\n"
        f"[{color}]{level}[/] deviation\n"
        f"  Z-score: [{color}]{deviation.z_score:+.2f}[/]\n"
        f"  Percentile: {deviation.percentile:.0f}%\n"
        f"  Change: {deviation.deviation_pct:+.1f}% from baseline\n"
        + (f"\n[dim italic]{deviation.clinical_note}[/]" if deviation.clinical_note else ""),
        title="Deviation Check",
        border_style=color,
    ))


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        console.print("[bold cyan]Soma CLI[/] - Personal Biosignal Dashboard\n")
        console.print("Commands:")
        console.print("  [cyan]status[/]                    Show system status and coverage")
        console.print("  [cyan]baselines[/]                 Show all computed baselines")
        console.print("  [cyan]signals[/] <biomarker> [days]  Show recent signals")
        console.print("  [cyan]check[/] <biomarker> <value>   Check value against baseline")
        console.print("\nExamples:")
        console.print("  python -m soma.cli status")
        console.print("  python -m soma.cli signals hrv_rmssd 14")
        console.print("  python -m soma.cli check hrv_rmssd 28.5")
        return

    cmd = sys.argv[1]

    if cmd == "status":
        cmd_status()
    elif cmd == "baselines":
        cmd_baselines()
    elif cmd == "signals":
        if len(sys.argv) < 3:
            console.print("[red]Usage: signals <biomarker_slug> [days][/]")
            return
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        cmd_signals(sys.argv[2], days)
    elif cmd == "check":
        if len(sys.argv) < 4:
            console.print("[red]Usage: check <biomarker_slug> <value>[/]")
            return
        cmd_check(sys.argv[2], float(sys.argv[3]))
    else:
        console.print(f"[red]Unknown command: {cmd}[/]")


if __name__ == "__main__":
    main()
