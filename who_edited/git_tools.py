import subprocess
from pathlib import Path
import json

def run_git_command(cmd_list, cwd):
    result = subprocess.run(cmd_list, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def get_blame_info(file_path: str, line_number: int):
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent

    blame_output = run_git_command(
        ["git", "blame", f"-L{line_number},{line_number}", file_path.name],
        cwd=repo_dir
    )
    commit_hash = blame_output.split()[0]
    return commit_hash, file_path, repo_dir


def get_commit_info(commit_hash: str, cwd):
    output = run_git_command(
        ["git", "show", "-s", "--format=%an|%ad|%s", commit_hash],
        cwd=cwd
    )
    author, date, msg = output.split("|")
    return {
        "author": author,
        "date": date,
        "message": msg,
        "hash": commit_hash
    }


def get_commit_diff(commit_hash, cwd):
    return run_git_command(["git", "show", commit_hash], cwd)


def get_blame_summary(file_path: str):
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent
    blame_output = run_git_command(["git", "blame", file_path.name], cwd=repo_dir)
    authors = {}
    for line in blame_output.splitlines():
        author = line.split('(')[1].split('  ')[0].strip()
        authors[author] = authors.get(author, 0) + 1
    return sorted(authors.items(), key=lambda x: -x[1])


def get_line_history(file_path, line_number):
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent
    return run_git_command(["git", "log", f"-L{line_number},{line_number}:{file_path.name}"], cwd=repo_dir)


def search_commits_by_keyword(file_path, keyword):
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent
    return run_git_command(["git", "log", "--pretty=format:%h %an %s", "--grep", keyword], cwd=repo_dir)


def get_recent_modified_files(repo_path):
    return run_git_command(["git", "log", "-n", "10", "--name-only", "--pretty=format:"], cwd=repo_path)


def get_blame_range(file_path, line_range: str):
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent
    start, end = line_range.split("-")
    return run_git_command(["git", "blame", f"-L{start},{end}", file_path.name], cwd=repo_dir)


def get_line_content(file_path, line_number):
    with open(file_path, "r") as f:
        lines = f.readlines()
    if 0 <= line_number - 1 < len(lines):
        return lines[line_number - 1].strip()
    return "Line not found."


#def get_github_url(file_path, line_number):
    # This assumes GitHub and https remote — can be expanded for GitLab
#    file_path = Path(file_path).resolve()
 #   repo_dir = file_path.parent
#    remote = run_git_command(["git", "config", "--get", "remote.origin.url"], cwd=repo_dir)
#
#    if remote.endswith(".git"):
#        remote = remote[:-4]
#    if remote.startswith("git@"):
#        remote = remote.replace("git@", "https://").replace(":", "/")
#
#    branch = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)
#    relative_path = file_path.relative_to(repo_dir.parent)

#    return f"{remote}/blame/{branch}/{relative_path}#L{line_number}"
def get_github_url(file_path, line_number):
    file_path = Path(file_path).resolve()
    repo_dir = file_path.parent
    remote = run_git_command(["git", "config", "--get", "remote.origin.url"], cwd=repo_dir)

    # Handle SSH URLs (git@bitbucket.org:user/repo.git)
    if remote.startswith("git@"):
        remote = remote.replace("git@", "")
        domain, path = remote.split(":", 1)
        remote = f"https://{domain}/{path}"
    
    # Handle HTTPS URLs
    elif remote.startswith("http"):
        remote = remote.replace(".git", "")

    # Ensure .git is stripped
    remote = remote.rstrip(".git")

    # Get current branch
    branch = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)

    # Determine relative file path from repo root
    repo_root = run_git_command(["git", "rev-parse", "--show-toplevel"], cwd=repo_dir)
    relative_path = file_path.relative_to(repo_root)

    # Construct final URL
    if "bitbucket.org" in remote:
        return f"{remote}/src/{branch}/{relative_path}#L{line_number}"
    else:
        return f"{remote}/blame/{branch}/{relative_path}#L{line_number}"


def get_git_blame(file_path, line_number):
    file_path = Path(file_path).resolve()
    repo_root = file_path.parent

    try:
        result = subprocess.run(
            ["git", "blame", f"-L{line_number},{line_number}", str(file_path.name)],
            cwd=repo_root,  # Run git in the file’s directory
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        line = result.stdout.strip()
        commit_hash = line.split()[0]
        return commit_hash, repo_root
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running git blame: {e.stderr}")


def get_commit_info(commit_hash, repo_root):
    result = subprocess.run(
        ["git", "show", "-s", "--format=%an|%ad|%s", commit_hash],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        text=True
    )
    author, date, msg = result.stdout.strip().split("|")
    return {"author": author, "date": date, "message": msg, "hash": commit_hash}

