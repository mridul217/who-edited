# who-edited

A powerful CLI tool that helps you find who edited a specific line of a file using git blame, with advanced code analytics, visualization, and AI-powered features.

## Features

### Core Features
- Get detailed information about who last edited a specific line
- View commit diffs and line content with syntax highlighting
- See a summary of contributors to a file
- Show full history for a specific line
- Search commits by keyword
- List recently modified files in a repository
- Show blame information for a range of lines

### Interactive Mode
- Terminal User Interface (TUI) for browsing blame information
- Navigate through files with cursor keys
- Easily view commit information for any line
- Toggle between file view and blame table

### Advanced Analytics
- Generate code ownership metrics for files/repositories
- Calculate "bus factor" risk analysis
- Create heatmaps showing which files change most frequently 
- Analyze commit patterns by author, day, and time
- Export comprehensive HTML reports with visualizations

### Code Review Platform Integration
- Link directly to GitHub/GitLab PRs that introduced changes
- Show review comments associated with specific files
- Open PRs in browser directly from the command line

### AI-powered Features
- Suggest reviewers based on expertise and content similarity
- Identify potentially risky changes based on historical patterns
- Find code experts for specific sections of code
- Analyze commit message patterns

## Installation

### Using pip

```bash
pip install who-edited
```

### From source

```bash
git clone https://github.com/yourusername/who-edited.git
cd who-edited
pip install -e .
```

## Usage Examples

### Basic Usage

Get information about who edited a specific line:
```bash
who-edited line app.py --line 42
```

Show diff and highlight the line:
```bash
who-edited line app.py --line 42 --diff --highlight
```

Get a summary of contributors to a file:
```bash
who-edited summary app.py
```

Show full history for a line:
```bash
who-edited history app.py 42
```

Search commits by keyword:
```bash
who-edited search app.py "fix bug"
```

Show recently modified files in the repository:
```bash
who-edited recent /path/to/repo
```

Show blame info for a range of lines:
```bash
who-edited blame-range app.py 10-20
```

### Interactive Mode

Launch the interactive TUI:
```bash
who-edited interactive app.py
```

### Analytics

Analyze code ownership:
```bash
who-edited ownership /path/to/repo --file app.py
```

Calculate bus factor:
```bash
who-edited bus-factor /path/to/repo
```

Generate file change heatmap:
```bash
who-edited heatmap /path/to/repo --timespan 3m
```

Generate comprehensive HTML report:
```bash
who-edited report /path/to/repo --output report.html
```

### Review and Expert Finding

Suggest reviewers for a file:
```bash
who-edited suggest-review app.py --content
```

Find experts for a section of code:
```bash
who-edited expert app.py --start 10 --end 50
```

Show review comments for a file:
```bash
who-edited review-comments app.py
```

### Pattern Analysis

Analyze commit patterns:
```bash
who-edited commit-patterns /path/to/repo --author "John Doe"
```

Analyze commit message patterns:
```bash
who-edited message-analysis /path/to/repo
```

Identify risky changes:
```bash
who-edited risk app.py
```

## Requirements

- Python 3.10+
- Git

## Dependencies

- typer[all]
- textual
- pandas
- matplotlib
- scikit-learn
- requests
- rich
- numpy

## Author

Created by [Your Name]

## License

This project is licensed under the [MIT License](LICENSE).
