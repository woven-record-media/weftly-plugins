---
description: One-shot setup for Weftly MCP + mppx wallet payments. Requires --wallet <name>.
---

Set up this Claude Code project to call the Weftly MCP server with automatic MPP payments from an mppx wallet.

Flags (parsed from user input): `$ARGUMENTS`

- **`--wallet <name>` / `-w <name>` (required)** — the mppx wallet name to use for payments. If not present, stop immediately and tell the user:

  > `/weftly-setup:weftly-setup` requires a wallet name. Run:
  > `/weftly-setup:weftly-setup --wallet <name>`
  >
  > Use the name of the mppx wallet you want Claude to pay from (`npx --yes mppx@^0.6.5 account list` shows all wallets on this machine).

  Do not guess, do not default. The wallet holds real funds.

Throughout the steps below, substitute `<WALLET>` with the value passed to `--wallet`.

**Runner note**: this plugin requires `mppx >= 0.6.5` (older versions ship a broken `--mcp` stdio mode). All `mppx` commands below are invoked via `npx --yes mppx@^0.6.5 ...`, which forces npx to fetch a 0.6.5+ build instead of silently reusing a stale cached version. No global install is required.

Run the steps below in order. Stop and surface the problem to the user on any failure — do **not** silently create wallets or paper over missing prerequisites.

## 1. Verify `npx` and a working mppx are available

Run `command -v npx`.

- If not found: tell the user to install Node.js (which ships with npx), then rerun `/weftly-setup:weftly-setup --wallet <name>`. Stop here.
- If found: run `npx --yes mppx@^0.6.5 --version`. The `@^0.6.5` constraint forces npx to fetch a build that has the upstream MCP stdio fixes (versions before 0.6.5 silently exit before responding to any JSON-RPC call). Report the resolved version.

  - If the command fails or reports a version `< 0.6.5`: stop and tell the user to either upgrade their pinned `mppx` or clear their npx cache, then rerun.

## 2. Verify the `<WALLET>` wallet exists

Run `npx --yes mppx@^0.6.5 account list`.

- If the output includes `<WALLET>`: continue.
- If not: stop. Print:

  > The `<WALLET>` wallet was not found in the mppx keychain. Wallets hold real funds — create or import it explicitly with one of:
  > - `npx --yes mppx@^0.6.5 account create` (new random key), entering `<WALLET>` at the name prompt
  > - Import an existing key by setting `MPPX_PRIVATE_KEY` env var, or restoring from a backup
  >
  > Then fund the wallet with USDC on Tempo mainnet and rerun `/weftly-setup:weftly-setup --wallet <WALLET>`.

  Do not create the wallet automatically.

## 3. Set `<WALLET>` as the default account

Run `npx --yes mppx@^0.6.5 account default --account <WALLET>`. Surface any error.

## 4. Register the mppx MCP server with Claude Code

mppx ships a built-in stdio MCP server (`mppx --mcp`) that exposes the `sign` tool used to satisfy MPP `payment_required` challenges. As of 0.6.5 the upstream bugs that prevented this from working unattended are fixed (`mppx@0.6.5` changelog: *"Fixed MCP stdio startup and returned structured CLI command results without writing raw tool output to stdout"*).

Register it user-scoped (idempotent), pinning to `^0.6.5` so a stale npx cache cannot resurrect a broken older version:

```bash
claude mcp remove mppx -s user 2>/dev/null || true
claude mcp add -s user mppx -- npx --yes mppx@^0.6.5 --mcp
```

Verify with `claude mcp list | grep mppx` — should show `mppx` `✓ Connected` pointing at `npx --yes mppx@^0.6.5 --mcp`.

## 5. Sync mppx's bundled skills

Run `npx --yes mppx@^0.6.5 skills add`.

This copies skill files (notably `mppx-sign.md`) into `~/.claude/skills/`, teaching Claude when and how to call the `mppx:sign` tool in response to `payment_required` errors from any MPP-speaking MCP server.

## 6. Register the Weftly MCP server with Claude Code

Register the Weftly HTTP MCP server at the user scope so it is available in every project (idempotent):

```bash
claude mcp remove weftly -s user 2>/dev/null || true
claude mcp add -s user --transport http weftly https://api.weftly.ai/mcp
```

Verify with `claude mcp list | grep weftly` — should show `weftly` pointing at `https://api.weftly.ai/mcp`.

## 7. Show the wallet balance

Run `npx --yes mppx@^0.6.5 account view --account <WALLET>` and surface the output verbatim so the user sees the current address and balance before their first paid call. Flag if the balance is clearly too low (e.g. $0.00) to complete a transcribe ($0.50 audio, $1.00 video).

## 8. Verify the payment loop with a $0.01 smoke test

Before the user attempts a real job (where a stuck payment costs $0.50–$2.00), prove the wallet → MPP → Weftly path actually settles end-to-end. Run:

```bash
npx --yes mppx@^0.6.5 https://api.weftly.ai/api/test
```

Expected output: `{"paid":true,"service":"weftly-worker"}`. This deducts $0.01 USDC from `<WALLET>` and confirms the full sign + broadcast + verify loop.

If the call returns `payment_required` repeatedly or "Payment verification failed", do **not** advise the user to retry their `transcribe` call. Likely causes:

- Wallet not funded on Tempo mainnet (`account view` showed only testnet balances).
- Wrong default account — re-check `account default` from step 3.
- `--rpc-url` needed for a non-standard endpoint (rare on mainnet).

Surface the failing output verbatim and stop, rather than burning the user's USDC on a real job that will hit the same block.

## 9. Print next steps

Tell the user, in plain text:

1. Run `/reload-plugins` (or restart Claude Code) — the new MCP servers and skills need to be loaded into the session.
2. Verify `mppx:sign` and `weftly:transcribe` appear in the available tool list.
3. Try a paid call, e.g.: "transcribe ./sample.mp3 using Weftly". Claude should handle the `payment_required` → `mppx:sign` → retry loop automatically.

## Notes

- Never skip step 2's manual-creation requirement, even if it would simplify onboarding. mppx wallets on mainnet hold real USDC; auto-creating a differently-named wallet would silently point Claude at an empty one and any new key would also need funding before paid calls can succeed.
- The `^0.6.5` pin in every `npx --yes mppx@^0.6.5 ...` invocation is deliberate: bare `npx mppx` will reuse whatever mppx the npx cache already resolved on this machine, which can be a much older version (e.g. 0.5.x) whose `--mcp` mode silently exits without responding. `^0.6.5` forces npx to fetch a build that includes the MCP stdio fix.
- Step 4 is idempotent: rerunning it just re-registers the MCP server. If `claude mcp list` already shows `mppx` pointing at `npx --yes mppx@^0.6.5 --mcp`, step 4 is effectively a no-op.
- For ad-hoc shell use (e.g. `account fund`, `account view`), invoke mppx with the same pin: `npx --yes mppx@^0.6.5 <subcommand>`.
- **`mppx <url>` vs `mppx sign`** — the bare HTTP wrapper (`mppx <url>`) signs **and** broadcasts the on-chain payment in one step, then retries the request. `mppx sign` only produces an offline-signed credential; sending that credential back to a Weftly endpoint without separately settling the underlying transaction will fail server-side verification with `Payment verification failed`. The smoke test in step 8 uses `mppx <url>` for exactly this reason. When debugging payment issues from the shell, prefer `mppx <url>` over `mppx sign`.
