import subprocess
from pathlib import Path
import os
import json
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union
from collections import defaultdict
import re
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from who_edited.git_tools import run_git_command
from who_edited.analytics import calculate_code_ownership


def get_commit_frequency_patterns(repo_path: str, author: Optional[str] = None, days: int = 90) -> Dict[str, Any]:
    """
    Analyze an author's commit frequency patterns.
    
    Args:
        repo_path: Path to the git repository
        author: Author to analyze (None for all authors)
        days: Number of days to analyze
        
    Returns:
        Dictionary with commit frequency metrics
    """
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    git_cmd = ["git", "log", f"--since={since_date}", "--format=%an|%ad|%s", "--date=iso"]
    if author:
        git_cmd.extend(["--author", author])
        
    output = run_git_command(git_cmd, cwd=repo_path)
    
    commit_data = []
    for line in output.splitlines():
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                author_name = parts[0]
                commit_date = datetime.fromisoformat(parts[1].strip().replace(" ", "T").replace(" -", "-").split(" +")[0])
                commit_data.append((author_name, commit_date))
    
    if not commit_data:
        return {"error": "No commit data found"}
    
    # Group commits by day of week
    days_of_week = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
    day_counts = defaultdict(int)
    hour_counts = defaultdict(int)
    
    for _, commit_date in commit_data:
        day_counts[days_of_week[commit_date.weekday()]] += 1
        hour_counts[commit_date.hour] += 1
    
    # Calculate time between commits
    author_commits = defaultdict(list)
    for author_name, commit_date in commit_data:
        author_commits[author_name].append(commit_date)
    
    time_between_commits = {}
    for author_name, dates in author_commits.items():
        if len(dates) <= 1:
            continue
            
        sorted_dates = sorted(dates)
        diffs = [(sorted_dates[i+1] - sorted_dates[i]).total_seconds() / 3600 for i in range(len(sorted_dates)-1)]
        
        if diffs:
            time_between_commits[author_name] = {
                "mean_hours": np.mean(diffs),
                "median_hours": np.median(diffs),
                "min_hours": min(diffs),
                "max_hours": max(diffs)
            }
    
    return {
        "total_commits": len(commit_data),
        "days_analyzed": days,
        "commits_by_day": dict(sorted(day_counts.items())),
        "commits_by_hour": dict(sorted(hour_counts.items())),
        "time_between_commits": time_between_commits
    }


def analyze_commit_messages(repo_path: str, author: Optional[str] = None, count: int = 100) -> Dict[str, Any]:
    """
    Analyze commit message patterns for an author.
    
    Args:
        repo_path: Path to the git repository
        author: Author to analyze (None for all authors)
        count: Number of commits to analyze
        
    Returns:
        Dictionary with commit message metrics
    """
    git_cmd = ["git", "log", f"-n{count}", "--format=%an|%s"]
    if author:
        git_cmd.extend(["--author", author])
        
    output = run_git_command(git_cmd, cwd=repo_path)
    
    messages = []
    for line in output.splitlines():
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                messages.append(parts[1])
    
    if not messages:
        return {"error": "No commit messages found"}
    
    # Calculate message length statistics
    lengths = [len(msg) for msg in messages]
    
    # Detect common patterns
    patterns = {
        "fix": len([m for m in messages if re.search(r'\bfix(ed|es|ing)?\b', m.lower())]),
        "feature": len([m for m in messages if re.search(r'\b(feature|feat)\b', m.lower())]),
        "refactor": len([m for m in messages if re.search(r'\brefactor(ing|ed)?\b', m.lower())]),
        "docs": len([m for m in messages if re.search(r'\bdoc(s|umentation)?\b', m.lower())]),
        "test": len([m for m in messages if re.search(r'\btest(s|ing)?\b', m.lower())]),
        "style": len([m for m in messages if re.search(r'\bstyle\b', m.lower())]),
        "deps": len([m for m in messages if re.search(r'\b(dependencies|deps)\b', m.lower())]),
    }
    
    # Find common words
    all_words = " ".join(messages).lower()
    word_counts = defaultdict(int)
    
    for word in re.findall(r'\b[a-z][a-z0-9]{2,}\b', all_words):
        if word not in ['the', 'and', 'for', 'with', 'this', 'that', 'from']:
            word_counts[word] += 1
    
    return {
        "total_messages": len(messages),
        "message_length": {
            "mean": np.mean(lengths),
            "median": np.median(lengths),
            "min": min(lengths),
            "max": max(lengths)
        },
        "common_patterns": patterns,
        "common_words": dict(sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    }


def identify_risky_changes(file_path: str) -> Dict[str, Any]:
    """
    Identify potentially risky changes in a file's history.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with risk metrics
    """
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent
    
    # Get file history
    output = run_git_command(
        ["git", "log", "--follow", "--name-status", file_path.name],
        cwd=repo_dir
    )
    
    # Look for potential risk indicators in commit history
    risk_indicators = {
        "large_changes": [],
        "quick_fixes": [],
        "unreviewed_changes": [],
        "multiple_authors": set()
    }
    
    commit_data = []
    current_commit = {}
    
    for line in output.splitlines():
        if line.startswith("commit "):
            if current_commit:
                commit_data.append(current_commit)
                
            current_commit = {"hash": line.split()[1]}
            
        elif line.startswith("Author: "):
            current_commit["author"] = line[8:].strip()
            risk_indicators["multiple_authors"].add(current_commit["author"])
            
        elif line.startswith("Date: "):
            current_commit["date"] = line[6:].strip()
            
        elif line and ":" not in line and not line.startswith(" "):
            message = line.strip()
            current_commit["message"] = message
            
            # Check for quick fix indicators in commit message
            if re.search(r'\b(hotfix|quick fix|emergency|urgent)\b', message.lower()):
                risk_indicators["quick_fixes"].append({
                    "hash": current_commit["hash"],
                    "message": message,
                    "date": current_commit.get("date", "")
                })
                
        elif line.startswith(("M", "A", "D")):
            current_commit["change_type"] = line[0]
    
    # Add the last commit
    if current_commit:
        commit_data.append(current_commit)
    
    # Get file change sizes
    for commit in commit_data:
        hash_value = commit.get("hash")
        if not hash_value:
            continue
            
        # Get the diff stats for this commit for this file
        try:
            stat_output = run_git_command(
                ["git", "show", "--stat", hash_value, "--", file_path.name],
                cwd=repo_dir
            )
            
            # Parse lines added/removed
            match = re.search(r'(\d+) insertion.+?(\d+) deletion', stat_output)
            if match:
                insertions = int(match.group(1))
                deletions = int(match.group(2))
                total_changes = insertions + deletions
                
                # Consider large changes (more than 100 lines changed)
                if total_changes > 100:
                    risk_indicators["large_changes"].append({
                        "hash": hash_value,
                        "insertions": insertions,
                        "deletions": deletions,
                        "total": total_changes,
                        "message": commit.get("message", ""),
                        "date": commit.get("date", "")
                    })
        except Exception:
            pass  # Skip if we can't get diff stats
    
    # Overall risk assessment
    risk_score = 0
    
    # More than 3 authors is higher risk (more knowledge distribution)
    risk_score += min(len(risk_indicators["multiple_authors"]) - 2, 5)
    
    # Large changes add to risk
    risk_score += min(len(risk_indicators["large_changes"]), 5) * 2
    
    # Quick fixes add to risk
    risk_score += min(len(risk_indicators["quick_fixes"]), 5) * 3
    
    risk_level = "Low"
    if risk_score > 10:
        risk_level = "High"
    elif risk_score > 5:
        risk_level = "Medium"
    
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_indicators": {
            "large_changes": risk_indicators["large_changes"],
            "quick_fixes": risk_indicators["quick_fixes"],
            "multiple_authors_count": len(risk_indicators["multiple_authors"])
        },
        "recommendations": generate_recommendations(risk_indicators)
    }


def generate_recommendations(risk_indicators: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on risk indicators."""
    recommendations = []
    
    if len(risk_indicators["multiple_authors"]) > 3:
        recommendations.append("Consider documenting code ownership for this file to clarify responsibilities.")
        
    if len(risk_indicators["large_changes"]) > 2:
        recommendations.append("Large changes detected. Consider breaking down changes into smaller, more manageable pieces.")
        
    if len(risk_indicators["quick_fixes"]) > 1:
        recommendations.append("Multiple 'quick fixes' found. Review if underlying issues need more thorough solutions.")
        
    if not recommendations:
        recommendations.append("No specific recommendations. File appears to have a healthy change history.")
        
    return recommendations


def suggest_reviewers_by_content(repo_path: str, file_content: str, exclude_authors: List[str] = None) -> List[Dict[str, Any]]:
    """
    Suggest reviewers based on content similarity to their previous work.
    
    Args:
        repo_path: Path to the git repository
        file_content: Content of the file to be reviewed
        exclude_authors: Authors to exclude from suggestions (e.g., the current author)
        
    Returns:
        List of suggested reviewers with similarity scores
    """
    if exclude_authors is None:
        exclude_authors = []
        
    # Get list of authors
    output = run_git_command(
        ["git", "shortlog", "-sne", "HEAD"],
        cwd=repo_path
    )
    
    authors = []
    for line in output.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            author = parts[1].strip()
            if author not in exclude_authors:
                authors.append(author)
    
    if not authors:
        return []
    
    # Get a sample of files touched by each author
    author_files = {}
    
    for author in authors:
        try:
            # Get files touched by this author
            files_output = run_git_command(
                ["git", "log", "--author", author, "--name-only", "--format=", "--max-count=100"],
                cwd=repo_path
            )
            
            author_files[author] = list(set(line for line in files_output.splitlines() if line.strip()))
        except Exception:
            continue
    
    # Collect file contents for similarity comparison
    author_content = {}
    
    for author, files in author_files.items():
        content_samples = []
        
        for file_path in files[:5]:  # Limit to 5 files per author for performance
            try:
                try:
                    full_path = os.path.join(repo_path, file_path)
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content_samples.append(f.read())
                except Exception:
                    # Get file content from git if the file doesn't exist locally
                    content = run_git_command(
                        ["git", "show", f"HEAD:{file_path}"],
                        cwd=repo_path
                    )
                    content_samples.append(content)
            except Exception:
                continue
                
        if content_samples:
            author_content[author] = "\n".join(content_samples)
    
    # Calculate content similarity using TF-IDF
    if not author_content:
        return []
        
    try:
        # Create document corpus with author samples and the target file
        documents = list(author_content.values())
        documents.append(file_content)
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer(analyzer='word', ngram_range=(1, 3), min_df=2, stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(documents)
        
        # Compare similarity of the target file to each author's content
        target_vector = tfidf_matrix[-1]
        author_vectors = tfidf_matrix[:-1]
        
        similarity_scores = cosine_similarity(target_vector, author_vectors).flatten()
        
        # Create list of authors with similarity scores
        authors_list = list(author_content.keys())
        similarity_results = [(authors_list[i], float(similarity_scores[i])) for i in range(len(authors_list))]
        
        # Sort by similarity score
        similarity_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return top matches with additional info
        result = []
        for author, score in similarity_results[:3]:  # Top 3 matches
            # Get additional expertise info
            ownership = calculate_code_ownership(repo_path, threshold=0.01)
            expertise = ownership.get(author, 0) * 100  # Convert to percentage
            
            result.append({
                "author": author,
                "similarity_score": score,
                "expertise_score": expertise,
                "combined_score": (score * 0.7) + (min(expertise, 20) / 20 * 0.3)  # Weight: 70% similarity, 30% expertise
            })
            
        return sorted(result, key=lambda x: x["combined_score"], reverse=True)
        
    except Exception as e:
        print(f"Error suggesting reviewers by content: {e}")
        return []


def get_expert_for_code_area(repo_path: str, file_path: str, line_start: int, line_end: int) -> List[Dict[str, Any]]:
    """
    Find the expert for a specific area of code.
    
    Args:
        repo_path: Path to the git repository
        file_path: Path to the file
        line_start: Start line number
        line_end: End line number
        
    Returns:
        List of experts with their expertise level
    """
    file_path = Path(file_path).resolve()
    
    try:
        # Get blame for the specific line range
        blame_output = run_git_command(
            ["git", "blame", f"-L{line_start},{line_end}", "-w", "-p", file_path.name],
            cwd=repo_path
        )
        
        author_lines = {}
        current_author = None
        
        for line in blame_output.splitlines():
            if line.startswith("author "):
                current_author = line[7:].strip()
                author_lines[current_author] = author_lines.get(current_author, 0) + 1
        
        total_lines = sum(author_lines.values())
        experts = []
        
        for author, count in sorted(author_lines.items(), key=lambda x: x[1], reverse=True):
            # Calculate additional metrics
            try:
                author_commits = run_git_command(
                    ["git", "log", "--author", author, "--pretty=format:%h", "--", file_path.name],
                    cwd=repo_path
                )
                commit_count = len(author_commits.splitlines())
            except Exception:
                commit_count = 0
                
            experts.append({
                "author": author,
                "lines_changed": count,
                "ownership_percentage": (count / total_lines) * 100 if total_lines > 0 else 0,
                "commit_count": commit_count,
                "expertise_level": determine_expertise_level(count, total_lines, commit_count)
            })
            
        return experts
        
    except Exception as e:
        print(f"Error finding expert: {e}")
        return []


def determine_expertise_level(lines_changed: int, total_lines: int, commit_count: int) -> str:
    """Determine expertise level based on lines changed and commit count."""
    ownership_pct = (lines_changed / total_lines) * 100 if total_lines > 0 else 0
    
    if ownership_pct > 70 or (ownership_pct > 50 and commit_count > 5):
        return "High"
    elif ownership_pct > 30 or (ownership_pct > 20 and commit_count > 3):
        return "Medium"
    else:
        return "Low" 