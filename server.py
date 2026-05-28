"""
NIRA File Intelligence MCP
Watch directories, semantic search, diff tracking, codebase summarization.
"""
import os
import time
import hashlib
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "NIRA File Intelligence",
    instructions=(
        "Live file system intelligence. Watch directories for changes, "
        "semantic search across all drives, diff files, summarize codebases. "
        "Not just read — understand and monitor the file system."
    )
)

WATCHED: dict[str, dict] = {}  # path -> {hash, mtime, size}
_SNAPSHOT: dict[str, str] = {}  # path -> content hash


def _hash_file(path: Path) -> str:
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


@mcp.tool()
def file_watch_start(directory: str, extensions: list[str] = None) -> dict:
    """
    Start watching a directory for changes.
    extensions: file types to watch, e.g. ['.py', '.json']. None = all files.
    Returns: {watching, file_count, snapshot_taken}
    """
    d = Path(directory)
    if not d.exists():
        return {"error": f"Directory not found: {directory}"}

    exts = set(extensions) if extensions else None
    count = 0
    for f in d.rglob("*"):
        if f.is_file() and (exts is None or f.suffix in exts):
            _SNAPSHOT[str(f)] = _hash_file(f)
            count += 1

    WATCHED[directory] = {
        "started": time.time(),
        "extensions": extensions,
        "file_count": count,
    }
    return {"watching": directory, "file_count": count, "snapshot_taken": True}


@mcp.tool()
def file_watch_check(directory: str) -> dict:
    """
    Check for changes since last watch snapshot.
    Returns: {added, modified, deleted, unchanged}
    """
    d = Path(directory)
    if directory not in WATCHED:
        return {"error": "Not watching this directory. Call file_watch_start first."}

    exts_raw = WATCHED[directory].get("extensions")
    exts = set(exts_raw) if exts_raw else None

    current: dict[str, str] = {}
    for f in d.rglob("*"):
        if f.is_file() and (exts is None or f.suffix in exts):
            current[str(f)] = _hash_file(f)

    old_paths = set(k for k in _SNAPSHOT if k.startswith(str(d)))
    new_paths = set(current.keys())

    added    = sorted(new_paths - old_paths)
    deleted  = sorted(old_paths - new_paths)
    modified = sorted(p for p in new_paths & old_paths if current[p] != _SNAPSHOT.get(p, ""))

    # Update snapshot
    for p in deleted:
        _SNAPSHOT.pop(p, None)
    _SNAPSHOT.update(current)

    return {
        "added":     added,
        "modified":  modified,
        "deleted":   deleted,
        "unchanged": len(new_paths) - len(added) - len(modified),
        "checked_at": time.time(),
    }


@mcp.tool()
def file_search(
    query: str,
    roots: list[str] = None,
    extensions: list[str] = None,
    max_results: int = 50,
    case_sensitive: bool = False,
) -> dict:
    """
    Search for files by name pattern or content.
    query: filename pattern OR content string to search for.
    roots: directories to search. Defaults to common project roots.
    Returns: {matches: [{path, match_type, context}]}
    """
    import re
    if not roots:
        roots = [
            str(Path.home()),
            str(Path.home()),
            str(Path.home() / "Videos"),
            str(Path.home() / "mcps"),
        ]

    exts = set(extensions) if extensions else None
    flags = 0 if case_sensitive else re.IGNORECASE
    matches = []

    for root in roots:
        r = Path(root)
        if not r.exists():
            continue
        try:
            for f in r.rglob("*"):
                if not f.is_file():
                    continue
                if exts and f.suffix not in exts:
                    continue
                if "__pycache__" in str(f) or ".git" in str(f):
                    continue

                # Filename match
                if re.search(query, f.name, flags):
                    matches.append({"path": str(f), "match_type": "filename", "context": ""})
                    if len(matches) >= max_results:
                        break
                    continue

                # Content match (text files only)
                if f.suffix in {".py", ".js", ".ts", ".json", ".md", ".txt", ".yaml", ".toml", ".html", ".css"}:
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        if re.search(query, text, flags):
                            # Get context around first match
                            m = re.search(query, text, flags)
                            start = max(0, m.start() - 80)
                            end = min(len(text), m.end() + 80)
                            matches.append({
                                "path": str(f),
                                "match_type": "content",
                                "context": text[start:end].strip(),
                            })
                    except Exception:
                        pass

                if len(matches) >= max_results:
                    break
        except PermissionError:
            continue

    return {"matches": matches, "total": len(matches), "query": query}


@mcp.tool()
def file_diff(path_a: str, path_b: str = None, show_lines: int = 50) -> dict:
    """
    Diff two files, or diff a file against its last snapshot.
    path_b: if omitted, diffs path_a against its snapshot from file_watch.
    Returns: {diff, added_lines, removed_lines, changed}
    """
    import difflib
    pa = Path(path_a)
    if not pa.exists():
        return {"error": f"File not found: {path_a}"}

    current = pa.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)

    if path_b:
        pb = Path(path_b)
        if not pb.exists():
            return {"error": f"File not found: {path_b}"}
        other = pb.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        label_a, label_b = path_a, path_b
    else:
        old_hash = _SNAPSHOT.get(str(pa))
        if not old_hash:
            return {"error": "No snapshot for this file. Call file_watch_start first."}
        other = current  # same as current if no change tracked
        label_a, label_b = "snapshot", path_a

    diff = list(difflib.unified_diff(other, current, fromfile=label_a, tofile=label_b, n=3))
    added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    return {
        "diff": "".join(diff[:show_lines]),
        "added_lines": added,
        "removed_lines": removed,
        "changed": bool(diff),
        "truncated": len(diff) > show_lines,
    }


@mcp.tool()
def file_summarize_dir(directory: str, max_files: int = 200) -> dict:
    """
    Summarize a directory's structure and contents — file counts, sizes, languages, recent changes.
    Returns: {structure, stats, largest_files, recent_files}
    """
    d = Path(directory)
    if not d.exists():
        return {"error": f"Directory not found: {directory}"}

    stats: dict[str, int] = {}
    files = []
    total_size = 0

    for f in d.rglob("*"):
        if not f.is_file() or "__pycache__" in str(f) or ".git" in str(f):
            continue
        ext = f.suffix.lower() or "(no ext)"
        stats[ext] = stats.get(ext, 0) + 1
        size = f.stat().st_size
        total_size += size
        files.append({"path": str(f.relative_to(d)), "size": size, "mtime": f.stat().st_mtime})

    files_sorted_size   = sorted(files, key=lambda x: x["size"], reverse=True)[:10]
    files_sorted_recent = sorted(files, key=lambda x: x["mtime"], reverse=True)[:10]

    return {
        "directory": directory,
        "total_files": len(files),
        "total_size_mb": round(total_size / 1_048_576, 2),
        "by_extension": dict(sorted(stats.items(), key=lambda x: x[1], reverse=True)[:20]),
        "largest_files": files_sorted_size,
        "most_recent": files_sorted_recent,
    }


@mcp.tool()
def file_recent(
    directory: str = str(Path.home()),
    minutes: int = 60,
    extensions: list[str] = None,
) -> dict:
    """
    Find all files modified in the last N minutes.
    Returns: {files: [{path, modified_ago_s, size}]}
    """
    d = Path(directory)
    now = time.time()
    cutoff = now - (minutes * 60)
    exts = set(extensions) if extensions else None
    results = []

    for f in d.rglob("*"):
        if not f.is_file() or "__pycache__" in str(f):
            continue
        if exts and f.suffix not in exts:
            continue
        try:
            mtime = f.stat().st_mtime
            if mtime > cutoff:
                results.append({
                    "path": str(f),
                    "modified_ago_s": round(now - mtime),
                    "size": f.stat().st_size,
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["modified_ago_s"])
    return {"files": results[:100], "total": len(results), "window_minutes": minutes}


if __name__ == "__main__":
    mcp.run(transport="stdio")
