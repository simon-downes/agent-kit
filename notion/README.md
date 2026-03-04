# notion

CLI tool for searching and fetching Notion pages via MCP.

## Purpose

`notion` provides command-line access to your Notion workspace through the Notion MCP (Model Context Protocol) server. Search your workspace and fetch page content with multiple output formats.

## Features

- Search across Notion workspace
- Fetch pages by ID, URL, or path
- Multiple output formats: terminal-rendered markdown, raw markdown, JSON
- OAuth authentication via oauth tool
- Async MCP client for efficient API calls

## Requirements

- `oauth` tool must be installed (for authentication)
- Python 3.13+
- Notion workspace with MCP access

## Installation

```bash
# Install globally
uv tool install git+https://github.com/simon-downes/cli-tools.git --subdirectory notion

# Or run directly without installing
uvx --from git+https://github.com/simon-downes/cli-tools.git --subdirectory notion notion --help
```

## Authentication

Before using the notion tool, authenticate with Notion:

```bash
# If oauth is installed
oauth login notion

# Or using uvx
uvx --from git+https://github.com/simon-downes/cli-tools.git --subdirectory oauth oauth login notion
```

This will open your browser to authorize the application and store credentials securely.

## Usage

### Search Notion

```bash
# Search with terminal-rendered markdown (default)
notion search "project planning"

# Search with raw markdown output
notion search "meeting notes" --raw

# Search with JSON output
notion search "budget" --json
```

### Fetch a Page

```bash
# Fetch by page ID
notion fetch 1f88a35c22c3809cae17dac118231cd4

# Fetch by full URL
notion fetch https://www.notion.so/My-Page-1f88a35c22c3809cae17dac118231cd4

# Fetch by path
notion fetch My-Page-1f88a35c22c3809cae17dac118231cd4

# Fetch with raw markdown
notion fetch 1f88a35c22c3809cae17dac118231cd4 --raw

# Fetch with JSON
notion fetch 1f88a35c22c3809cae17dac118231cd4 --json
```

## Output Formats

### Default (Terminal Markdown)

Renders markdown with syntax highlighting and formatting using rich:

```bash
notion fetch 1f88a35c22c3809cae17dac118231cd4
```

Output is formatted for terminal viewing with:
- Syntax-highlighted code blocks
- Formatted headers
- Styled lists and quotes

### Raw Markdown (`--raw`)

Outputs plain markdown text, suitable for piping to files or other tools:

```bash
notion fetch 1f88a35c22c3809cae17dac118231cd4 --raw > page.md
```

### JSON (`--json`)

Outputs the raw MCP response as JSON:

```bash
notion search "api docs" --json | jq '.[] | select(.type == "text")'
```

## Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication error (not logged in, invalid credentials) |
| 3 | Notion API error (page not found, rate limit, etc.) |

## Examples

**Note:** Examples assume tools are installed globally. If using `uvx`, prefix commands with the full `uvx --from git+...` syntax shown in the installation section.

### Save Page to File

```bash
notion fetch 1f88a35c22c3809cae17dac118231cd4 --raw > my-page.md
```

### Search and Process Results

```bash
# Get search results as JSON and extract page IDs
notion search "project" --json | jq -r '.[] | select(.type == "text") | .text'
```

### Check Authentication

```bash
# If not authenticated, you'll see:
notion search "test"
# Error: Not authenticated with Notion
# Run: uvx oauth login notion
```

### Fetch Multiple Pages

```bash
#!/bin/bash
for page_id in "id1" "id2" "id3"; do
  echo "Fetching $page_id..."
  notion fetch "$page_id" --raw > "page-$page_id.md"
done
```

## Error Handling

### Authentication Errors (Exit Code 2)

```bash
notion search "test"
# Error: Not authenticated with Notion
# Run: uvx oauth login notion
```

Solution: Run `uvx oauth login notion` to authenticate.

### API Errors (Exit Code 3)

```bash
notion fetch invalid-page-id
# Error: Page not found
```

Common API errors:
- Page not found
- Insufficient permissions
- Rate limit exceeded
- Invalid page ID format

## Technical Details

### Architecture

- **CLI Framework:** click for command structure
- **MCP Client:** mcp package for Notion MCP server communication
- **Auth:** OAuth credentials via oauth tool
- **Output:** rich for terminal markdown rendering
- **Async:** asyncio for efficient MCP communication

### MCP Server

Connects to: `https://mcp.notion.com/mcp`

Uses Notion MCP tools:
- `notion-search` - Search workspace
- `notion-fetch` - Fetch page content

### Dependencies

- `click>=8.1.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting
- `mcp>=1.0.0` - MCP client library

### Development

```bash
# Run tests
cd notion && uv run pytest -v

# Type check
uv run mypy src/

# Lint and format
uv run ruff check .
uv run black .
```

### Project Structure

```
notion/
├── pyproject.toml
├── README.md
├── src/notion/
│   ├── __init__.py
│   ├── cli.py      # CLI commands
│   ├── auth.py     # OAuth credential fetching
│   ├── mcp.py      # MCP connection logic
│   └── output.py   # Output formatting
└── tests/
    └── test_output.py  # Output formatting tests
```

## Limitations

- Requires Notion workspace with MCP access
- Search requires Notion AI for cross-tool search (Slack, Google Drive, etc.)
- Rate limits apply (see [Notion MCP documentation](https://developers.notion.com/guides/mcp/mcp-supported-tools))

## Future Enhancements

- Support for creating and updating pages
- Database queries
- Comment management
- Batch operations
