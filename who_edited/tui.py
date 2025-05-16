from textual.app import App
from textual.widgets import Header, Footer, Static, DataTable
from textual.reactive import reactive
from textual.binding import Binding
from pathlib import Path
import asyncio

from who_edited.git_tools import (
    get_blame_info, 
    get_commit_info, 
    get_line_content, 
    get_github_url,
    get_blame_range
)

class CommitInfo(Static):
    """Widget to display commit information."""
    commit_data = reactive({})
    
    def render(self):
        if not self.commit_data:
            return "No commit selected"
            
        return f"""
# Commit: {self.commit_data.get('hash', 'Unknown')}
* Author: {self.commit_data.get('author', 'Unknown')}
* Date: {self.commit_data.get('date', 'Unknown')}
* Message: {self.commit_data.get('message', 'Unknown')}
        """

class FileViewer(Static):
    """Widget to display file content with blame information."""
    file_path = reactive("")
    current_line = reactive(1)
    content = reactive([])
    
    async def watch_current_line(self, line):
        """Watch for line changes and update commit info."""
        if not self.file_path or not self.content:
            return
            
        try:
            commit_hash, _, repo_dir = get_blame_info(self.file_path, line)
            commit_info = get_commit_info(commit_hash, repo_dir)
            self.app.query_one(CommitInfo).commit_data = commit_info
        except Exception as e:
            self.app.query_one(CommitInfo).commit_data = {"message": f"Error: {e}"}
    
    def render(self):
        """Render the file with the currently selected line highlighted."""
        if not self.content:
            return "No file loaded"
            
        result = []
        for i, line in enumerate(self.content, 1):
            if i == self.current_line:
                result.append(f"[bold yellow]{i}: {line}[/]")
            else:
                result.append(f"{i}: {line}")
                
        return "\n".join(result)
    
    def load_file(self, path):
        """Load a file and its content."""
        self.file_path = str(path)
        with open(path, "r") as f:
            self.content = f.read().splitlines()
            
    def move_up(self):
        """Move cursor up one line."""
        if self.current_line > 1:
            self.current_line -= 1
            
    def move_down(self):
        """Move cursor down one line."""
        if self.current_line < len(self.content):
            self.current_line += 1


class BlameTable(DataTable):
    """DataTable to display blame information for a range of lines."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_column("Line")
        self.add_column("Author")
        self.add_column("Date")
        self.add_column("Commit")
        self.add_column("Content")
        
    async def load_blame_data(self, file_path, line_range=None):
        """Load blame data for the specified file and line range."""
        self.clear()
        
        file_path = Path(file_path)
        if not file_path.exists():
            return
            
        if line_range is None:
            # Default to first 20 lines
            line_range = "1-20"
            
        try:
            blame_output = get_blame_range(file_path, line_range)
            lines = blame_output.splitlines()
            
            for line in lines:
                parts = line.split(")")
                commit_info = parts[0] + ")"  # Everything before the first closing parenthesis
                
                # Extract line number (before the closing parenthesis)
                line_number = commit_info.split()[-1].strip()
                
                # Extract author from between the first opening parenthesis and the next space
                author = commit_info.split("(")[1].split()[0]
                
                # Extract date (YYYY-MM-DD) - simplified approach
                date_parts = [part for part in commit_info.split() if "-" in part]
                date = date_parts[0] if date_parts else "Unknown"
                
                # Extract commit hash (first part of the line)
                commit_hash = commit_info.split()[0]
                
                # Extract content (everything after the closing parenthesis)
                code_content = ")".join(parts[1:]).strip()
                
                self.add_row(line_number, author, date, commit_hash, code_content)
        except Exception as e:
            self.add_row("Error", str(e), "", "", "")


class WhoEditedTUI(App):
    """Interactive TUI for the who-edited tool."""
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("o", "open_in_browser", "Open in browser"),
        Binding("t", "toggle_view", "Toggle view"),
    ]
    
    def __init__(self, file_path=None):
        super().__init__()
        self.file_path = file_path
        self.view_mode = "file"  # "file" or "blame"
        
    async def on_mount(self):
        """Set up UI when app is mounted."""
        self.header = Header()
        self.file_viewer = FileViewer()
        self.blame_table = BlameTable()
        self.commit_info = CommitInfo()
        
        await self.view.dock(self.header, edge="top")
        await self.view.dock(self.commit_info, edge="bottom", size=6)
        
        # Start with file view
        await self.view.dock(self.file_viewer, edge="left")
        
        if self.file_path:
            self.file_viewer.load_file(self.file_path)
            await self.blame_table.load_blame_data(self.file_path)
            
    async def action_cursor_up(self):
        """Handle cursor up action."""
        if self.view_mode == "file":
            self.file_viewer.move_up()
            
    async def action_cursor_down(self):
        """Handle cursor down action."""
        if self.view_mode == "file":
            self.file_viewer.move_down()
            
    async def action_open_in_browser(self):
        """Open the current file and line in browser (GitHub/GitLab)."""
        if self.file_path and self.view_mode == "file":
            try:
                url = get_github_url(self.file_path, self.file_viewer.current_line)
                import webbrowser
                webbrowser.open(url)
            except Exception as e:
                self.commit_info.commit_data = {"message": f"Error opening URL: {e}"}
                
    async def action_toggle_view(self):
        """Toggle between file view and blame table view."""
        if self.view_mode == "file":
            self.view_mode = "blame"
            await self.view.dock(self.blame_table, edge="left")
        else:
            self.view_mode = "file"
            await self.view.dock(self.file_viewer, edge="left")


def run_tui(file_path):
    """Run the TUI with the given file path."""
    app = WhoEditedTUI(file_path)
    app.run() 