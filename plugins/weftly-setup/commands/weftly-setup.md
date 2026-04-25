---
description: One-shot setup for Weftly MCP + mppx wallet payments. Requires --wallet <name>.
---

Set up this Claude Code project to call the Weftly MCP server with automatic MPP payments from an mppx wallet.

Flags (parsed from user input): `$ARGUMENTS`

- **`--wallet <name>` / `-w <name>` (required)** — the mppx wallet name to use for payments. If not present, stop immediately and tell the user:

  > `/weftly-setup:weftly-setup` requires a wallet name. Run:
  > `/weftly-setup:weftly-setup --wallet <name>`
  >
  > Use the name of the mppx wallet you want Claude to pay from (`npx mppx account list` shows all wallets on this machine).

  Do not guess, do not default. The wallet holds real funds.

Throughout the steps below, substitute `<WALLET>` with the value passed to `--wallet`.

**Runner note**: all `mppx` commands below are invoked via `npx mppx ...`. No global install is required. mppx 0.6.5+ runs its own MCP stdio server via `--mcp`; step 4 registers it directly with Claude Code.

Run the steps below in order. Stop and surface the problem to the user on any failure — do **not** silently create wallets or paper over missing prerequisites.

## 1. Verify `npx` is available

Run `command -v npx`.

- If not found: tell the user to install Node.js (which ships with npx), then rerun `/weftly-setup:weftly-setup --wallet <name>`. Stop here.
- If found: run `npx --yes mppx --version` to both confirm mppx is reachable and warm the npx cache. Report the version.

## 2. Verify the `<WALLET>` wallet exists

Run `npx mppx account list`.

- If the output includes `<WALLET>`: continue.
- If not: stop. Print:

  > The `<WALLET>` wallet was not found in the mppx keychain. Wallets hold real funds — create or import it explicitly with one of:
  > - `npx mppx account create` (new random key), entering `<WALLET>` at the name prompt
  > - Import an existing key by setting `MPPX_PRIVATE_KEY` env var, or restoring from a backup
  >
  > Then fund the wallet with USDC on Tempo mainnet and rerun `/weftly-setup:weftly-setup --wallet <WALLET>`.

  Do not create the wallet automatically.

## 3. Set `<WALLET>` as the default account

Run `npx mppx account default --account <WALLET>`. Surface any error.

## 4. Register mppx `--mcp` with Claude Code

Check the mppx version from step 1.

- If the version is **< 0.6.5**: stop and tell the user:

  > mppx 0.6.5 or later is required. Upgrade with:
  > ```
  > npx clear-npx-cache
  > npx --yes mppx@latest --version
  > ```
  > Then rerun `/weftly-setup:weftly-setup --wallet <WALLET>`.

- If the version is **≥ 0.6.5**: register mppx's built-in MCP stdio server with Claude Code (idempotent):

  ```bash
  claude mcp remove mppx -s user 2>/dev/null || true
  claude mcp add -s user mppx -- npx --yes mppx --mcp
  ```

Verify with `claude mcp list | grep mppx` — should show `mppx` pointing at `npx --yes mppx --mcp`.

## 5. Sync mppx's bundled skills

Run `npx mppx skills add`.

This copies skill files (notably `mppx-sign.md`) into `~/.claude/skills/`, teaching Claude when and how to call the `mppx:sign` tool in response to `payment_required` errors from any MPP-speaking MCP server.

## 6. Register the Weftly MCP server with Claude Code

Register the Weftly HTTP MCP server at the user scope so it is available in every project (idempotent):

```bash
claude mcp remove weftly -s user 2>/dev/null || true
claude mcp add -s user --transport http weftly https://api.weftly.ai/mcp
```

Verify with `claude mcp list | grep weftly` — should show `weftly` pointing at `https://api.weftly.ai/mcp`.

## 7. Show the wallet balance

Run `npx mppx account view --account <WALLET>` and surface the output verbatim so the user sees the current address and balance before their first paid call. Flag if the balance is clearly too low (e.g. $0.00) to complete a transcribe ($0.50 audio, $1.00 video).

## 8. Print next steps

Tell the user, in plain text:

1. Restart Claude Code — the new MCP servers and skills only load on a fresh session.
2. After restart, verify `mppx:sign` and `weftly:transcribe` appear in the available tool list.
3. Try a paid call, e.g.: "transcribe ./sample.mp3 using Weftly". Claude should handle the `payment_required` → `mppx:sign` → retry loop automatically.

## Notes

- Never skip step 2's manual-creation requirement, even if it would simplify onboarding. mppx wallets on mainnet hold real USDC; auto-creating a differently-named wallet would silently point Claude at an empty one and any new key would also need funding before paid calls can succeed.
- mppx 0.6.5 fixed the stdio startup and structured-output bugs (wevm/mppx PR #391); versions before 0.6.5 are not supported by this skill.
- Step 4 is idempotent: rerunning it re-registers the MCP server. If `claude mcp list` already shows `mppx` pointing at `npx --yes mppx --mcp`, step 4 is a no-op in effect.
