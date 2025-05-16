# who_edited/cli.py
import typer
import json
import webbrowser
import tempfile
import os
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from datetime import datetime

from who_edited.git_tools import (
    get_blame_info,
    get_commit_info,
    get_commit_diff,
    get_blame_summary,
    get_line_history,
    search_commits_by_keyword,
    get_recent_modified_files,
    get_blame_range,
    get_line_content,
    get_github_url,
    get_git_blame,
)

# Import new modules
from who_edited.tui import run_tui
from who_edited.analytics import (
    get_repo_contributors, 
    calculate_code_ownership, 
    analyze_bus_factor, 
    generate_file_heatmap,
    export_html_report,
    suggest_reviewers,
)
from who_edited.platform_integration import (
    get_pr_for_file_line,
    get_review_comments_for_file,
    open_pr_page_for_line,
)
from who_edited.ai_features import (
    identify_risky_changes,
    get_commit_frequency_patterns,
    analyze_commit_messages,
    suggest_reviewers_by_content,
    get_expert_for_code_area,
)

app = typer.Typer(help="Git blame helper CLI with advanced analytics")
console = Console()

@app.command()
def line(
        file: str = typer.Argument(..., help="File path"),
        line: int = typer.Option(..., "--line", "-l", help="Line number"),
        diff: bool = typer.Option(False, "--diff", help="Show commit diff"),
        json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
        web: bool = typer.Option(False, "--web", help="Open GitHub blame URL in browser"),
        highlight: bool = typer.Option(False, "--highlight", help="Show line content"),
        pr: bool = typer.Option(False, "--pr", help="Show PR information that introduced this line"),
):
    """Get who edited a specific line of a file."""
    try:
        commit_hash, file_path, repo_dir = get_blame_info(file, line)
        commit_info = get_commit_info(commit_hash, repo_dir)

        output = {
            "line": line,
            "file": file_path.name,
            "commit": commit_info,
        }

        if highlight:
            output["line_content"] = get_line_content(file_path, line)

        if web:
            url = get_github_url(file_path, line)
            typer.echo(f"Opening in browser: {url}")
            webbrowser.open(url)
            return
            
        if pr:
            pr_info = get_pr_for_file_line(file_path, line)
            if pr_info:
                output["pr"] = {
                    "number": pr_info.get("number") or pr_info.get("iid"),
                    "title": pr_info.get("title"),
                    "url": pr_info.get("html_url") or pr_info.get("web_url"),
                    "author": pr_info.get("user", {}).get("login") or pr_info.get("author", {}).get("username"),
                }
                if not json_out:
                    typer.echo(f"\nPull Request: #{output['pr']['number']}")
                    typer.echo(f"Title: {output['pr']['title']}")
                    typer.echo(f"Author: {output['pr']['author']}")
                    typer.echo(f"URL: {output['pr']['url']}")

        if json_out:
            typer.echo(json.dumps(output, indent=2))
        else:
            typer.echo(f"Line {line} in {file_path.name} last modified by: {commit_info['author']}")
            typer.echo(f"Commit: {commit_info['hash']}")
            typer.echo(f"Date: {commit_info['date']}")
            typer.echo(f"Message: {commit_info['message']}")
            if highlight:
                typer.echo(f"Code: {output['line_content']}")

            if diff:
                diff_text = get_commit_diff(commit_hash, repo_dir)
                typer.echo("\nCommit Diff:\n" + diff_text)

    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)


@app.command()
def summary(file: str = typer.Argument(..., help="File path to summarize")):
    """Show summary of who edited how many lines in a file."""
    try:
        summary_data = get_blame_summary(file)
        typer.echo(f"Blame summary for {file}:")
        for author, count in summary_data:
            typer.echo(f"  {author}: {count} lines")
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)


@app.command()
def history(file: str = typer.Argument(..., help="File path"), line: int = typer.Argument(..., help="Line number")):
    """Show full git log history for a specific line."""
    try:
        log = get_line_history(file, line)
        typer.echo(log)
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)


@app.command()
def search(file: str = typer.Argument(..., help="File path"), keyword: str = typer.Argument(..., help="Keyword to search in commits")):
    """Search commit messages by keyword for a file."""
    try:
        results = search_commits_by_keyword(file, keyword)
        if results.strip():
            typer.echo(f"Commits matching '{keyword}':\n{results}")
        else:
            typer.echo("No commits found matching that keyword.")
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)


@app.command()
def recent(repo_path: str = typer.Argument(..., help="Path to git repository")):
    """List recently modified files in the repo."""
    try:
        files = get_recent_modified_files(repo_path)
        if files.strip():
            files_list = sorted(set(files.splitlines()))
            typer.echo("Recently modified files:")
            for f in files_list:
                typer.echo(f"  {f}")
        else:
            typer.echo("No recent file changes found.")
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)


@app.command()
def blame_range(file: str = typer.Argument(..., help="File path"), line_range: str = typer.Argument(..., help="Line range (e.g. 10-20)")):
    """Show blame info for a range of lines."""
    try:
        output = get_blame_range(file, line_range)
        typer.echo(output)
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)


# New commands for added features

@app.command()
def interactive(file: str = typer.Argument(..., help="File path to view interactively")):
    """Launch an interactive TUI to explore file blame information."""
    try:
        run_tui(file)
    except Exception as e:
        typer.secho(f"Error launching interactive mode: {e}", fg=typer.colors.RED, err=True)


@app.command()
def ownership(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    file_path: Optional[str] = typer.Option(None, "--file", "-f", help="Specific file to analyze"),
    threshold: float = typer.Option(0.05, "--threshold", "-t", help="Minimum ownership percentage to show (0.0-1.0)"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Analyze code ownership for a repository or specific file."""
    try:
        ownership_data = calculate_code_ownership(repo_path, file_path, threshold)
        
        if json_out:
            typer.echo(json.dumps(ownership_data, indent=2))
        else:
            target = file_path if file_path else "repository"
            table = Table(title=f"Code Ownership for {target}")
            table.add_column("Author", style="cyan")
            table.add_column("Ownership %", justify="right", style="green")
            
            for author, percentage in sorted(ownership_data.items(), key=lambda x: x[1], reverse=True):
                table.add_row(author, f"{percentage:.2%}")
                
            console.print(table)
            
    except Exception as e:
        typer.secho(f"Error analyzing code ownership: {e}", fg=typer.colors.RED, err=True)


@app.command()
def bus_factor(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Threshold for critical ownership (0.0-1.0)"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Analyze the 'bus factor' of a repository."""
    try:
        analysis = analyze_bus_factor(repo_path, threshold)
        
        if json_out:
            typer.echo(json.dumps(analysis, indent=2))
        else:
            console.print(f"[bold]Bus Factor:[/bold] {analysis['bus_factor']}")
            console.print(f"[bold]Risk Level:[/bold] {analysis['risk_level']}")
            
            if analysis.get("critical_owners"):
                console.print("\n[bold]Critical Knowledge Owners:[/bold]")
                table = Table()
                table.add_column("Author", style="cyan")
                table.add_column("Ownership %", justify="right", style="green")
                
                for owner in analysis["critical_owners"]:
                    table.add_row(owner["author"], f"{owner['ownership']:.2%}")
                    
                console.print(table)
                
    except Exception as e:
        typer.secho(f"Error analyzing bus factor: {e}", fg=typer.colors.RED, err=True)


@app.command()
def heatmap(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    timespan: str = typer.Option("6m", "--timespan", "-t", help="Time span to analyze (e.g. 1w, 1m, 6m, 1y)"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of files to show"),
):
    """Generate a heatmap of file changes in the repository."""
    try:
        data = generate_file_heatmap(repo_path, timespan)
        
        if json_out:
            typer.echo(json.dumps(dict(sorted(data.items(), key=lambda x: x[1], reverse=True)[:limit]), indent=2))
        else:
            console.print(f"[bold]File Change Frequency (last {timespan}):[/bold]")
            table = Table()
            table.add_column("File", style="cyan")
            table.add_column("Changes", justify="right", style="green")
            
            for file_path, count in sorted(data.items(), key=lambda x: x[1], reverse=True)[:limit]:
                table.add_row(file_path, str(count))
                
            console.print(table)
            
    except Exception as e:
        typer.secho(f"Error generating heatmap: {e}", fg=typer.colors.RED, err=True)


@app.command()
def report(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Path to save the report"),
    open_browser: bool = typer.Option(True, "--open", help="Open the report in browser"),
):
    """Generate a comprehensive HTML report with visualizations."""
    try:
        if not output_path:
            # Generate a temporary file if no output path is provided
            output_path = os.path.join(tempfile.gettempdir(), f"git_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            
        report_path = export_html_report(repo_path, output_path)
        console.print(f"[green]Report generated at:[/green] {report_path}")
        
        if open_browser:
            console.print("[green]Opening report in browser...[/green]")
            webbrowser.open(f"file://{os.path.abspath(report_path)}")
            
    except Exception as e:
        typer.secho(f"Error generating report: {e}", fg=typer.colors.RED, err=True)


@app.command()
def suggest_review(
    file_path: str = typer.Argument(..., help="File path to suggest reviewers for"),
    count: int = typer.Option(3, "--count", "-c", help="Number of reviewers to suggest"),
    content_based: bool = typer.Option(False, "--content", help="Use content-based similarity (requires sklearn)"),
):
    """Suggest reviewers for a file based on history and expertise."""
    try:
        file_path = Path(file_path).resolve()
        repo_path = file_path.parent
        
        if content_based:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
                
                reviewers = suggest_reviewers_by_content(repo_path, file_content)
                
                if not reviewers:
                    raise ValueError("Could not suggest reviewers using content similarity")
                    
                console.print("[bold]Suggested Reviewers (content-based):[/bold]")
                table = Table()
                table.add_column("Author", style="cyan")
                table.add_column("Similarity", justify="right", style="green")
                table.add_column("Expertise", justify="right", style="yellow")
                
                for reviewer in reviewers:
                    table.add_row(
                        reviewer["author"],
                        f"{reviewer['similarity_score']:.2f}",
                        f"{reviewer['expertise_score']:.1f}%"
                    )
                    
                console.print(table)
                
            except Exception as e:
                console.print(f"[yellow]Content-based analysis failed: {e}[/yellow]")
                console.print("[yellow]Falling back to history-based analysis[/yellow]")
                content_based = False
        
        if not content_based:
            reviewers = suggest_reviewers(repo_path, file_path, count)
            
            console.print("[bold]Suggested Reviewers (history-based):[/bold]")
            for reviewer in reviewers:
                console.print(f"[cyan]{reviewer}[/cyan]")
                
    except Exception as e:
        typer.secho(f"Error suggesting reviewers: {e}", fg=typer.colors.RED, err=True)


@app.command()
def risk(
    file_path: str = typer.Argument(..., help="File path to analyze for risk"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Analyze risk factors for a file based on its change history."""
    try:
        risk_data = identify_risky_changes(file_path)
        
        if json_out:
            typer.echo(json.dumps(risk_data, indent=2))
        else:
            console.print(f"[bold]Risk Analysis for {file_path}[/bold]")
            console.print(f"Risk Score: {risk_data['risk_score']}")
            console.print(f"Risk Level: [{'red' if risk_data['risk_level'] == 'High' else 'yellow' if risk_data['risk_level'] == 'Medium' else 'green'}]{risk_data['risk_level']}[/]")
            
            console.print("\n[bold]Risk Indicators:[/bold]")
            indicators = risk_data["risk_indicators"]
            
            console.print(f"• [cyan]Multiple Authors:[/cyan] {indicators['multiple_authors_count']}")
            console.print(f"• [cyan]Large Changes:[/cyan] {len(indicators['large_changes'])}")
            console.print(f"• [cyan]Quick Fixes:[/cyan] {len(indicators['quick_fixes'])}")
            
            if len(indicators['large_changes']) > 0:
                console.print("\n[bold]Large Changes:[/bold]")
                for change in indicators['large_changes'][:3]:  # Show top 3
                    console.print(f"  • {change['insertions']} insertions, {change['deletions']} deletions ({change['date']})")
                    console.print(f"    {change['message']}")
            
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in risk_data["recommendations"]:
                console.print(f"• {rec}")
                
    except Exception as e:
        typer.secho(f"Error analyzing risk: {e}", fg=typer.colors.RED, err=True)


@app.command()
def expert(
    file_path: str = typer.Argument(..., help="File path to find experts for"),
    line_start: int = typer.Option(None, "--start", "-s", help="Start line number"),
    line_end: int = typer.Option(None, "--end", "-e", help="End line number"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Find code experts for a file or section of code."""
    try:
        file_path = Path(file_path).resolve()
        repo_path = file_path.parent
        
        # If no line range is specified, use the whole file
        if line_start is None or line_end is None:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                line_count = sum(1 for _ in f)
                
            line_start = 1
            line_end = line_count
            
        experts = get_expert_for_code_area(repo_path, file_path, line_start, line_end)
        
        if json_out:
            typer.echo(json.dumps(experts, indent=2))
        else:
            console.print(f"[bold]Code Experts for {file_path.name} (lines {line_start}-{line_end}):[/bold]")
            
            table = Table()
            table.add_column("Author", style="cyan")
            table.add_column("Lines", justify="right")
            table.add_column("Ownership %", justify="right")
            table.add_column("Commits", justify="right")
            table.add_column("Expertise", justify="center", style="green")
            
            for expert in experts:
                table.add_row(
                    expert["author"],
                    str(expert["lines_changed"]),
                    f"{expert['ownership_percentage']:.1f}%",
                    str(expert["commit_count"]),
                    expert["expertise_level"]
                )
                
            console.print(table)
            
    except Exception as e:
        typer.secho(f"Error finding experts: {e}", fg=typer.colors.RED, err=True)


@app.command()
def review_comments(
    file_path: str = typer.Argument(..., help="File path to get review comments for"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Get code review comments for a file from GitHub/GitLab."""
    try:
        comments = get_review_comments_for_file(file_path)
        
        if json_out:
            typer.echo(json.dumps(comments, indent=2))
        else:
            if not comments:
                console.print("[yellow]No review comments found for this file[/yellow]")
                return
                
            console.print(f"[bold]Review Comments for {file_path}:[/bold]")
            
            for i, comment in enumerate(comments, 1):
                console.print(f"\n[cyan]Comment #{i}[/cyan]")
                console.print(f"[bold]Author:[/bold] {comment['author']}")
                console.print(f"[bold]Line:[/bold] {comment.get('line', 'N/A')}")
                console.print(f"[bold]PR/MR:[/bold] #{comment.get('pr_number', comment.get('mr_number', 'N/A'))} - {comment.get('pr_title', comment.get('mr_title', 'N/A'))}")
                console.print(f"[bold]Date:[/bold] {comment.get('date', 'N/A')}")
                console.print(f"[bold]Comment:[/bold]\n{comment['body']}")
                
    except Exception as e:
        typer.secho(f"Error getting review comments: {e}", fg=typer.colors.RED, err=True)


@app.command()
def commit_patterns(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Specific author to analyze"),
    days: int = typer.Option(90, "--days", "-d", help="Number of days to analyze"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Analyze commit frequency patterns for authors."""
    try:
        patterns = get_commit_frequency_patterns(repo_path, author, days)
        
        if json_out:
            typer.echo(json.dumps(patterns, indent=2))
        else:
            title = f"Commit Patterns for {'all authors' if author is None else author}"
            console.print(f"[bold]{title} (last {days} days)[/bold]")
            console.print(f"Total Commits: {patterns['total_commits']}")
            
            console.print("\n[bold]Commits by Day:[/bold]")
            for day, count in patterns['commits_by_day'].items():
                console.print(f"  {day}: {count}")
                
            console.print("\n[bold]Commits by Hour (24h):[/bold]")
            hours_data = patterns['commits_by_hour']
            for hour in range(24):
                count = hours_data.get(str(hour), 0)
                bar = "█" * (count // 2 + 1) if count > 0 else ""
                console.print(f"  {hour:02d}:00 | {bar} {count}")
                
            if patterns.get('time_between_commits'):
                console.print("\n[bold]Time Between Commits:[/bold]")
                for author, metrics in patterns['time_between_commits'].items():
                    console.print(f"  [cyan]{author}[/cyan]:")
                    console.print(f"    Avg: {metrics['mean_hours']:.1f} hours")
                    console.print(f"    Min: {metrics['min_hours']:.1f} hours")
                    console.print(f"    Max: {metrics['max_hours']:.1f} hours")
                    
    except Exception as e:
        typer.secho(f"Error analyzing commit patterns: {e}", fg=typer.colors.RED, err=True)


@app.command()
def message_analysis(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Specific author to analyze"),
    count: int = typer.Option(100, "--count", "-c", help="Number of commits to analyze"),
    json_out: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Analyze commit message patterns for authors."""
    try:
        analysis = analyze_commit_messages(repo_path, author, count)
        
        if json_out:
            typer.echo(json.dumps(analysis, indent=2))
        else:
            title = f"Commit Message Analysis for {'all authors' if author is None else author}"
            console.print(f"[bold]{title} (last {count} commits)[/bold]")
            
            msg_len = analysis['message_length']
            console.print(f"Total Messages: {analysis['total_messages']}")
            console.print(f"Avg Length: {msg_len['mean']:.1f} chars (min: {msg_len['min']}, max: {msg_len['max']})")
            
            console.print("\n[bold]Common Patterns:[/bold]")
            patterns = analysis['common_patterns']
            for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    percentage = (count / analysis['total_messages']) * 100
                    console.print(f"  {pattern}: {count} ({percentage:.1f}%)")
                    
            console.print("\n[bold]Common Words:[/bold]")
            words = analysis['common_words']
            for word, count in sorted(words.items(), key=lambda x: x[1], reverse=True)[:10]:
                console.print(f"  {word}: {count}")
                
    except Exception as e:
        typer.secho(f"Error analyzing commit messages: {e}", fg=typer.colors.RED, err=True)


if __name__ == "__main__":
    app()




