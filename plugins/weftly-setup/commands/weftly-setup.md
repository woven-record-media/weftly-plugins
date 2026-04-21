---
description: One-shot setup for Weftly MCP + mppx wallet payments. Requires --wallet <name>.
---

Set up this Claude Code project to call the Weftly MCP server with automatic MPP payments from an mppx wallet.

Flags (parsed from user input): `$ARGUMENTS`

- **`--wallet <name>` / `-w <name>` (required)** — the mppx wallet name to use for payments. If not present, stop immediately and tell the user:

  > `/weftly-setup` requires a wallet name. Run:
  > `/weftly-setup --wallet <name>`
  >
  > Use the name of the mppx wallet you want Claude to pay from (`npx mppx account list` shows all wallets on this machine).

  Do not guess, do not default. The wallet holds real funds.

Throughout the steps below, substitute `<WALLET>` with the value passed to `--wallet`.

**Runner note**: all `mppx` commands below are invoked via `npx mppx ...`. No global install is required. `mppx mcp add` will register the MCP server spawn command as `npx mppx --mcp`, so Claude Code will pull mppx on-demand on every launch (cached by npx after first run).

Run the steps below in order. Stop and surface the problem to the user on any failure — do **not** silently create wallets or paper over missing prerequisites.

## 1. Verify `npx` is available

Run `command -v npx`.

- If not found: tell the user to install Node.js (which ships with npx), then rerun `/weftly-setup --wallet <name>`. Stop here.
- If found: run `npx --yes mppx --version` to both confirm mppx is reachable and warm the npx cache. Report the version.

## 2. Verify the `<WALLET>` wallet exists

Run `npx mppx account list`.

- If the output includes `<WALLET>`: continue.
- If not: stop. Print:

  > The `<WALLET>` wallet was not found in the mppx keychain. Wallets hold real funds — create or import it explicitly with one of:
  > - `npx mppx account create` (new random key), entering `<WALLET>` at the name prompt
  > - Import an existing key by setting `MPPX_PRIVATE_KEY` env var, or restoring from a backup
  >
  > Then fund the wallet with USDC on Tempo mainnet and rerun `/weftly-setup --wallet <WALLET>`.

  Do not create the wallet automatically.

## 3. Set `<WALLET>` as the default account

Run `npx mppx account default --account <WALLET>`. Surface any error.

## 4. Register mppx as an MCP server in Claude Code

Run `npx mppx mcp add --agent claude-code`.

This writes a `mppx` entry into Claude Code's MCP config with the spawn command `npx mppx --mcp` (stdio). On Claude Code launch, that spawns the mppx MCP server in-process, exposing `mppx:sign`, `mppx:account-*`, etc. directly to Claude.

## 5. Sync mppx's bundled skills

Run `npx mppx skills add`.

This copies skill files (notably `mppx-sign.md`) into `~/.claude/skills/`, teaching Claude when and how to call the `mppx:sign` tool in response to `payment_required` errors from any MPP-speaking MCP server.

## 6. Ensure the Weftly MCP server is in `.mcp.json`

The Weftly MCP server URL is `https://api.weftly.ai/mcp`.

Check for `.mcp.json` in the current working directory.

- If it does not exist: create it with:
  ```json
  {
    "mcpServers": {
      "weftly": {
        "type": "http",
        "url": "https://api.weftly.ai/mcp"
      }
    }
  }
  ```
- If it exists and already has a `weftly` entry whose `url` matches `https://api.weftly.ai/mcp`: leave it alone.
- If it exists and has a `weftly` entry with a **different** URL: surface the mismatch and ask the user whether to overwrite.
- If it exists without a `weftly` entry: add the entry, preserving existing servers.

## 7. Show the wallet balance

Run `npx mppx account view --account <WALLET>` and surface the output verbatim so the user sees the current address and balance before their first paid call. Flag if the balance is clearly too low (e.g. $0.00) to complete a transcribe ($0.50 audio, $1.00 video).

## 8. Print next steps

Tell the user, in plain text:

1. Restart Claude Code — the new MCP servers and skills only load on a fresh session.
2. After restart, verify `mppx:sign` and `weftly:transcribe` appear in the available tool list.
3. Try a paid call, e.g.: "transcribe ./sample.mp3 using Weftly". Claude should handle the `payment_required` → `mppx:sign` → retry loop automatically.

## Notes

- Never skip step 2's manual-creation requirement, even if it would simplify onboarding. mppx wallets on mainnet hold real USDC; auto-creating a differently-named wallet would silently point Claude at an empty one and any new key would also need funding before paid calls can succeed.
- npx caches packages after first fetch; subsequent Claude Code launches spawn mppx quickly. If you want to pin a specific version, you can rerun step 4 with `--command "npx mppx@<version> --mcp"`.
- If `mppx mcp add` reports the server is already registered, treat that as success — it's idempotent.
