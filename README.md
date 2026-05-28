# NIRA File Intel MCP

> Smart file intelligence for Claude — search, deduplicate, organize, and analyze files

[![PyPI version](https://badge.fury.io/py/nira-file-intel.svg)](https://pypi.org/project/nira-file-intel/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick Start

```bash
pip install nira-file-intel
```

Add to your Claude Code MCP config (`~/.claude.json`):
```json
{
  "mcpServers": {
    "nira-file-intel": {
      "command": "python",
      "args": ["-m", "nira_file_intel"]
    }
  }
}
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `FILE_INTEL_ROOT` | Optional | Default root directory to search (default: home dir) |

## License

MIT — built by [pachote](https://github.com/pachote)
