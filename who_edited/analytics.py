import subprocess
from pathlib import Path
import json
import re
from collections import defaultdict, Counter
from datetime import datetime
import tempfile
import os
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

from who_edited.git_tools import run_git_command


def get_repo_contributors(repo_path: str) -> Dict[str, int]:
    """Get all contributors to a repository with their commit counts."""
    output = run_git_command(
        ["git", "shortlog", "-sne", "HEAD"],
        cwd=repo_path
    )
    
    contributors = {}
    for line in output.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            count = int(parts[0].strip())
            author = parts[1].strip()
            contributors[author] = count
            
    return contributors


def generate_contribution_timeline(repo_path: str, file_path: Optional[str] = None) -> pd.DataFrame:
    """Generate a timeline of contributions to a file or repository."""
    cmd = ["git", "log", "--pretty=format:%h|%an|%ad|%s", "--date=short"]
    
    if file_path:
        file_path = Path(file_path).resolve()
        cmd.append("--")
        cmd.append(str(file_path))
        
    output = run_git_command(cmd, cwd=repo_path)
    
    data = []
    for line in output.splitlines():
        if "|" in line:
            commit_hash, author, date, message = line.split("|", 3)
            data.append({
                "hash": commit_hash,
                "author": author,
                "date": datetime.strptime(date, "%Y-%m-%d"),
                "message": message
            })
            
    return pd.DataFrame(data)


def calculate_code_ownership(repo_path: str, file_path: Optional[str] = None, threshold: float = 0.05) -> Dict[str, float]:
    """
    Calculate code ownership percentages.
    
    Args:
        repo_path: Path to the git repository
        file_path: Optional specific file path to analyze
        threshold: Minimum percentage to include in results (e.g., 0.05 = 5%)
        
    Returns:
        Dictionary mapping authors to their ownership percentage
    """
    if file_path:
        file_path = Path(file_path).resolve()
        cmd = ["git", "blame", "--line-porcelain", str(file_path)]
        cwd = repo_path
    else:
        cmd = ["git", "ls-files", "|", "xargs", "git", "blame", "--line-porcelain"]
        cwd = repo_path
        
    try:
        result = subprocess.run(
            " ".join(cmd),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Error running git command: {result.stderr}")
            
        authors = []
        for line in result.stdout.splitlines():
            if line.startswith("author "):
                author = line[len("author "):].strip()
                authors.append(author)
                
        total_lines = len(authors)
        if total_lines == 0:
            return {}
            
        ownership = Counter(authors)
        ownership_percent = {author: count/total_lines for author, count in ownership.items()}
        
        # Filter out authors below threshold
        return {author: pct for author, pct in ownership_percent.items() if pct >= threshold}
        
    except Exception as e:
        print(f"Error calculating code ownership: {e}")
        return {}


def analyze_bus_factor(repo_path: str, critical_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Analyze the "bus factor" of a repository.
    
    The bus factor represents how many people need to be "hit by a bus" 
    before a project is in serious trouble due to lack of knowledge.
    
    Args:
        repo_path: Path to git repository
        critical_threshold: Threshold to consider critical ownership
        
    Returns:
        Dictionary with bus factor analysis
    """
    ownership = calculate_code_ownership(repo_path)
    if not ownership:
        return {"error": "No ownership data available"}
        
    # Sort owners by ownership percentage (descending)
    sorted_owners = sorted(ownership.items(), key=lambda x: x[1], reverse=True)
    
    # Calculate cumulative ownership
    cumulative = 0.0
    bus_factor = 0
    critical_owners = []
    
    for author, pct in sorted_owners:
        cumulative += pct
        bus_factor += 1
        
        if pct >= critical_threshold:
            critical_owners.append({
                "author": author,
                "ownership": pct
            })
            
        if cumulative >= 0.8:  # Standard threshold of 80%
            break
            
    return {
        "bus_factor": bus_factor,
        "critical_owners": critical_owners,
        "risk_level": "High" if bus_factor <= 2 else "Medium" if bus_factor <= 4 else "Low"
    }


def generate_file_heatmap(repo_path: str, timespan: str = "6m") -> Dict[str, int]:
    """
    Generate a heatmap data showing which files change most frequently.
    
    Args:
        repo_path: Path to git repository
        timespan: Time span to analyze (e.g., '1w', '1m', '6m', '1y')
        
    Returns:
        Dictionary mapping file paths to change frequencies
    """
    # Convert timespan to git-compatible format
    if timespan.endswith('d'):
        git_time = f"{timespan[:-1]} days ago"
    elif timespan.endswith('w'):
        git_time = f"{timespan[:-1]} weeks ago"
    elif timespan.endswith('m'):
        git_time = f"{timespan[:-1]} months ago"
    elif timespan.endswith('y'):
        git_time = f"{timespan[:-1]} years ago"
    else:
        git_time = "6 months ago"  # Default
        
    output = run_git_command(
        ["git", "log", f"--since={git_time}", "--name-only", "--pretty=format:"],
        cwd=repo_path
    )
    
    # Count file occurrences
    files = [line for line in output.splitlines() if line.strip()]
    return dict(Counter(files))


def export_html_report(repo_path: str, output_path: str) -> str:
    """
    Generate an HTML report with contributor analytics.
    
    Args:
        repo_path: Path to git repository
        output_path: Path to save the HTML report
        
    Returns:
        Path to the generated HTML file
    """
    # Get repository data
    contributors = get_repo_contributors(repo_path)
    timeline_df = generate_contribution_timeline(repo_path)
    ownership = calculate_code_ownership(repo_path, threshold=0.02)
    bus_factor = analyze_bus_factor(repo_path)
    heatmap = generate_file_heatmap(repo_path)
    
    # Generate visualizations
    temp_dir = tempfile.mkdtemp()
    
    # Contributors pie chart
    plt.figure(figsize=(8, 6))
    labels = [author for author in contributors.keys()]
    sizes = [count for count in contributors.values()]
    plt.pie(sizes, labels=labels, autopct='%1.1f%%')
    plt.title('Contribution Distribution')
    contributors_chart = os.path.join(temp_dir, "contributors.png")
    plt.savefig(contributors_chart)
    plt.close()
    
    # Timeline chart
    if not timeline_df.empty:
        plt.figure(figsize=(12, 6))
        # Group by date and author, count commits
        timeline = timeline_df.groupby([timeline_df['date'].dt.date, 'author']).size().unstack().fillna(0)
        timeline.plot(kind='bar', stacked=True)
        plt.title('Commit Timeline')
        plt.xticks(rotation=45)
        plt.tight_layout()
        timeline_chart = os.path.join(temp_dir, "timeline.png")
        plt.savefig(timeline_chart)
        plt.close()
    else:
        timeline_chart = None
    
    # Ownership bar chart
    plt.figure(figsize=(10, 6))
    sorted_ownership = sorted(ownership.items(), key=lambda x: x[1], reverse=True)
    authors = [item[0] for item in sorted_ownership]
    percentages = [item[1] * 100 for item in sorted_ownership]  # Convert to percentages
    
    plt.barh(authors, percentages)
    plt.xlabel('Ownership Percentage')
    plt.title('Code Ownership Distribution')
    plt.tight_layout()
    ownership_chart = os.path.join(temp_dir, "ownership.png")
    plt.savefig(ownership_chart)
    plt.close()
    
    # File heatmap (top 20 files)
    plt.figure(figsize=(12, 8))
    top_files = sorted(heatmap.items(), key=lambda x: x[1], reverse=True)[:20]
    files = [os.path.basename(item[0]) for item in top_files]
    changes = [item[1] for item in top_files]
    
    plt.barh(files, changes)
    plt.xlabel('Number of Changes')
    plt.title('Most Frequently Changed Files')
    plt.tight_layout()
    heatmap_chart = os.path.join(temp_dir, "heatmap.png")
    plt.savefig(heatmap_chart)
    plt.close()
    
    # Generate HTML report
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Git Repository Analysis</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .section {{ margin-bottom: 30px; }}
            .chart {{ margin: 20px 0; text-align: center; }}
            .bus-factor {{ padding: 15px; background-color: #f8f9fa; border-radius: 5px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Git Repository Analysis</h1>
            <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="section">
                <h2>Contributors</h2>
                <table>
                    <tr>
                        <th>Author</th>
                        <th>Commits</th>
                    </tr>
                    {"".join(f"<tr><td>{author}</td><td>{count}</td></tr>" for author, count in sorted(contributors.items(), key=lambda x: x[1], reverse=True))}
                </table>
                
                <div class="chart">
                    <img src="file://{contributors_chart}" alt="Contributors Distribution">
                </div>
            </div>
            
            <div class="section">
                <h2>Code Ownership</h2>
                <table>
                    <tr>
                        <th>Author</th>
                        <th>Ownership Percentage</th>
                    </tr>
                    {"".join(f"<tr><td>{author}</td><td>{pct:.2%}</td></tr>" for author, pct in sorted(ownership.items(), key=lambda x: x[1], reverse=True))}
                </table>
                
                <div class="chart">
                    <img src="file://{ownership_chart}" alt="Code Ownership Distribution">
                </div>
            </div>
            
            <div class="section">
                <h2>Bus Factor Analysis</h2>
                <div class="bus-factor">
                    <p><strong>Bus Factor:</strong> {bus_factor.get('bus_factor', 'N/A')}</p>
                    <p><strong>Risk Level:</strong> {bus_factor.get('risk_level', 'N/A')}</p>
                    <h3>Critical Knowledge Owners:</h3>
                    <table>
                        <tr>
                            <th>Author</th>
                            <th>Ownership Percentage</th>
                        </tr>
                        {"".join(f"<tr><td>{item['author']}</td><td>{item['ownership']:.2%}</td></tr>" for item in bus_factor.get('critical_owners', []))}
                    </table>
                </div>
            </div>
            
            <div class="section">
                <h2>Commit Timeline</h2>
                {f'<div class="chart"><img src="file://{timeline_chart}" alt="Commit Timeline"></div>' if timeline_chart else '<p>No timeline data available</p>'}
            </div>
            
            <div class="section">
                <h2>File Change Frequency (Top 20)</h2>
                <table>
                    <tr>
                        <th>File</th>
                        <th>Changes</th>
                    </tr>
                    {"".join(f"<tr><td>{file}</td><td>{count}</td></tr>" for file, count in sorted(heatmap.items(), key=lambda x: x[1], reverse=True)[:20])}
                </table>
                
                <div class="chart">
                    <img src="file://{heatmap_chart}" alt="File Change Frequency">
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Write HTML to file
    with open(output_path, 'w') as f:
        f.write(html_content)
        
    return output_path


def suggest_reviewers(repo_path: str, file_path: str, count: int = 3) -> List[str]:
    """
    Suggest potential reviewers for a file based on ownership and contribution history.
    
    Args:
        repo_path: Path to git repository
        file_path: Path to the file needing review
        count: Number of reviewers to suggest
        
    Returns:
        List of suggested reviewers
    """
    file_path = Path(file_path).resolve()
    
    # Get file ownership
    ownership = calculate_code_ownership(repo_path, file_path)
    
    # Get recent contributors to the file
    output = run_git_command(
        ["git", "log", "-n", "10", "--pretty=format:%an", "--", str(file_path)],
        cwd=repo_path
    )
    
    recent_contributors = [line for line in output.splitlines() if line.strip()]
    
    # Build a score for each potential reviewer
    scores = defaultdict(float)
    
    # Weight ownership heavily
    for author, pct in ownership.items():
        scores[author] += pct * 10  # Weight ownership 10x
        
    # Weight recent contributions
    for author in recent_contributors:
        scores[author] += 1
        
    # Sort by score and return top reviewers
    return [author for author, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:count]] 