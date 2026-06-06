# galah-mcp

An [MCP](https://modelcontextprotocol.io) server exposing the
[`galah`](https://galah.ala.org.au/Python/) library from the **Atlas of Living
Australia (ALA)** as tools for LLM assistants (Claude Desktop, etc.).

> **Proof of concept.** This is an experimental MCP proof of concept, not an
> official or production-ready project. Expect rough edges and breaking changes;
> use it to explore what an MCP over `galah` can do, not as a stable dependency.

It's a working v1 skeleton: taxon search, counts, occurrence downloads, species
lists, and field exploration.

## Exposed tools

| Tool                 | galah function         | Purpose                                            |
|----------------------|------------------------|----------------------------------------------------|
| `set_config`         | `galah_config()`       | Set email + atlas (required to download)           |
| `search_taxa`        | `search_taxa()`        | Resolve a name → taxonomic identifier              |
| `atlas_counts`       | `atlas_counts()`       | Count records (fast; do this before downloading)   |
| `atlas_occurrences`  | `atlas_occurrences()`  | Download occurrences (inline sample + full CSV)    |
| `atlas_species`      | `atlas_species()`      | List species in a group/region                     |
| `search_fields`      | `search_all(fields=)`  | Discover valid fields for filters                  |
| `show_field_values`  | `show_values()`        | See admissible values for a field                  |
| `list_atlases`       | `show_all(atlases=)`   | List available atlases                             |

## Installation

```bash
cd galah-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
# or without packaging:
pip install "mcp[cli]" galah-python pandas
```

## Configuration

Downloading occurrences requires an email **registered with the chosen atlas**
(see below). You can configure via environment variables (applied at startup):

```bash
export GALAH_EMAIL="you@example.com"
export GALAH_ATLAS="Australia"     # default; or Spain (gbif.es), GBIF, Austria, etc.
export GALAH_REASON="4"            # 4 = scientific research
export GALAH_DOWNLOAD_DIR="./galah_downloads"
```

…or at runtime by calling the `set_config` tool.

`GALAH_EMAIL` must be an email address that has been registered with the chosen
atlas. The default atlas is **ALA (Australia)**; for the ALA you can register at
<https://auth.ala.org.au/userdetails/registration/createAccount>. Other portals
(e.g. `Spain` / gbif.es) use their own accounts. Run `list_atlases` to see all
supported portals.

## Quick setup for Claude Code (user scope)

From this folder, on your machine:

```bash
./setup.sh
```

It creates `.venv`, installs the server, and registers `galah` in Claude Code at
user scope (defaults: `GALAH_EMAIL=john.doe@example.org`, `GALAH_ATLAS=Australia`).
Override with `GALAH_EMAIL=... GALAH_ATLAS=... ./setup.sh`. Verify with `claude mcp list`
or `/mcp` inside Claude Code. Manual config for other clients is below.

## Use with MCP clients

The server speaks MCP over **stdio**, so it works with any MCP-compatible client.
The command is always "run `server.py` with the Python that has `galah-python`
installed". Use an **absolute path to the venv Python** to avoid PATH surprises:

```
/absolute/path/to/galah-mcp/.venv/bin/python   /absolute/path/to/galah-mcp/server.py
```

In the examples below, replace the paths and your email accordingly.

### Claude Desktop

Edit `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "galah": {
      "command": "/absolute/path/to/galah-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/galah-mcp/server.py"],
      "env": {
        "GALAH_EMAIL": "you@example.com",
        "GALAH_ATLAS": "Australia"
      }
    }
  }
}
```

### Claude Code

Add it from the CLI (project scope writes a shareable `.mcp.json`):

```bash
claude mcp add galah \
  --scope project \
  --transport stdio \
  --env GALAH_EMAIL=you@example.com \
  --env GALAH_ATLAS=Australia \
  -- /absolute/path/to/galah-mcp/.venv/bin/python /absolute/path/to/galah-mcp/server.py
```

That produces a `.mcp.json` like:

```json
{
  "mcpServers": {
    "galah": {
      "type": "stdio",
      "command": "/absolute/path/to/galah-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/galah-mcp/server.py"],
      "env": { "GALAH_EMAIL": "you@example.com", "GALAH_ATLAS": "Australia" }
    }
  }
}
```

Check it with `/mcp` inside Claude Code.

### OpenCode

In `opencode.json` (project root) or `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "galah": {
      "type": "local",
      "command": ["/absolute/path/to/galah-mcp/.venv/bin/python", "/absolute/path/to/galah-mcp/server.py"],
      "enabled": true,
      "environment": {
        "GALAH_EMAIL": "you@example.com",
        "GALAH_ATLAS": "Australia"
      }
    }
  }
}
```

### OpenAI Codex CLI

Add it from the CLI:

```bash
codex mcp add galah \
  --env GALAH_EMAIL=you@example.com \
  --env GALAH_ATLAS=Australia \
  -- /absolute/path/to/galah-mcp/.venv/bin/python /absolute/path/to/galah-mcp/server.py
```

Or edit `~/.codex/config.toml` directly:

```toml
[mcp_servers.galah]
command = "/absolute/path/to/galah-mcp/.venv/bin/python"
args = ["/absolute/path/to/galah-mcp/server.py"]

[mcp_servers.galah.env]
GALAH_EMAIL = "you@example.com"
GALAH_ATLAS = "Australia"
```

List active servers with `/mcp` in the Codex TUI.

### Other clients (Cursor, VS Code, Windsurf, Zed, …)

They all use the same `mcpServers` JSON shape as Claude Desktop (`command` +
`args` + `env`). Point `command` at the venv Python and `args` at `server.py`.

## Quick check (without an MCP client)

```bash
# Official MCP inspector — lists tools and lets you call them by hand
mcp dev server.py
```

## Typical flow

1. `set_config(email=...)` — once.
2. `search_taxa("Vulpes vulpes")` — get the taxon.
3. `atlas_counts(taxa="Vulpes vulpes", filters=["year=2023"])` — estimate volume.
4. `atlas_occurrences(taxa="Vulpes vulpes", filters=["year=2023"])` — download.

## Tests

```bash
pip install -e ".[test]"      # or: pip install pytest
pytest                         # offline tests (no network, fast)

# Live equivalence tests against the real ALA API (opt-in):
GALAH_LIVE=1 GALAH_EMAIL="you@example.com" pytest
```

The offline suite injects a fake galah and checks that every tool returns exactly
the same records as the underlying DataFrame — i.e. the MCP layer is transparent.
The live suite verifies the tool output matches a direct galah call and that
`atlas_counts` agrees with the number of rows from `atlas_occurrences`.

## Design notes

- Large downloads (> `max_inline_rows`, default 50) are saved to CSV and only a
  sample is returned, to avoid flooding the model context.
- All galah functions return a `pandas.DataFrame`; here they are serialized to JSON.
- Only `atlas_occurrences` needs an email; the rest of the tools don't.
