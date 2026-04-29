# Weftly Plugins for Claude Code

Official Claude Code plugins for [Weftly](https://weftly.ai) — agent-native transcription, summarization, and more. Plugins in this marketplace wire Claude Code up to call the Weftly MCP server with automatic [MPP](https://mpp.dev) payments from your own mppx wallet.

## Install the marketplace

In Claude Code:

```
/plugin marketplace add woven-record-media/weftly-plugins
```

## Plugins

### `weftly-setup`

One-shot setup for the Weftly MCP server and mppx wallet payments. Registers the `mppx` stdio MCP server so Claude can sign payment challenges, syncs the mppx skills, and adds the Weftly HTTP MCP server to your project's `.mcp.json`.

**Prerequisites:**

- **Node.js** (ships with `npx`)
- An **mppx wallet** funded with USDC on Tempo mainnet.

**1. Create and fund an mppx wallet**

```
npx mppx account create
```

Choose a name when prompted (you'll pass it to `/weftly-setup:weftly-setup` below). Then fund the wallet with USDC on Tempo mainnet — see [mppx docs](https://mpp.dev/sdk/typescript) for funding, or bridge from Base using [this guide](https://github.com/woven-record-media/weftly-monorepo/blob/main/docs/bridge-usdc-base-to-tempo.md).

**2. Install the plugin:**

```
/plugin install weftly-setup@weftly
```

**3. Run setup with your wallet name:**

```
/weftly-setup:weftly-setup --wallet <your-wallet-name>
```

The `--wallet` flag is required — no silent defaults, because mppx wallets hold real funds. The name must match a wallet in your mppx keychain (see `npx mppx account list`).

#### What `/weftly-setup:weftly-setup` does

1. Checks that `npx` is available and warms the mppx cache.
2. Verifies the named wallet exists in the mppx keychain.
3. Sets it as the default mppx account.
4. Installs a small local MCP stdio proxy (`~/.claude/mppx-mcp-proxy.mjs`) that shells out to `npx --yes mppx sign` per call, and registers it with Claude Code as the `mppx` MCP server (`claude mcp add -s user mppx -- node ~/.claude/mppx-mcp-proxy.mjs`). The proxy is a workaround for [wevm/mppx#386](https://github.com/wevm/mppx/issues/386) and [#387](https://github.com/wevm/mppx/issues/387), which currently make mppx's own `--mcp` mode unusable from MCP clients.
5. Syncs mppx's bundled skills into `~/.claude/skills/` so Claude knows to call `mppx:sign` on `payment_required` errors (`npx mppx skills add`).
6. Adds a `weftly` entry to the project's `.mcp.json` pointing at the Weftly MCP server.
7. Prints your wallet balance.
8. Prompts you to restart Claude Code.

After restart, Claude Code gains:

- `weftly:transcribe`, `weftly:summarize`, `weftly:complete_upload`, `weftly:get_job_status` (and any future Weftly tools) from the remote HTTP MCP server.
- `mppx:sign` from the local stdio MCP proxy. (Other mppx operations — `account list`, `account fund`, etc. — remain available via `npx mppx <subcommand>` directly in a shell; the proxy intentionally only exposes `sign`, since that's what the unattended payment flow needs.)

When Claude calls a paid Weftly tool, the flow is fully automatic: Weftly returns `payment_required` with a challenge → Claude calls `mppx:sign` (signed against your wallet) → Claude retries the Weftly call with the credential → the tool proceeds.

### `weftly-setup-dev`

Same shape as `weftly-setup`, but pointed at the **dev** environment (`api.dev.weftly.ai`) and a **testnet** wallet on Tempo Moderato (chain 42431). Use this when you are building or testing Weftly itself with a fake-money wallet — never for production work.

**Prerequisites:**

- **Node.js** (ships with `npx`)
- **mppx 0.6.7 or later** — earlier versions ignore the challenge's `chainId: 42431` and try to send the tx on Tempo mainnet, failing with insufficient balance.
- An **mppx wallet** with **testnet PathUSD** on Tempo Moderato (chain 42431). The wallet's mainnet USDC balance is irrelevant on dev.

**1. Create and fund a testnet mppx wallet**

```
npx mppx account create
```

Pick a wallet name (e.g. `weftly-test`). Fund it with testnet PathUSD from the Tempo Moderato faucet at https://moderato.tempo.xyz/faucet, or ask in the team's #weftly-dev channel.

**2. Install the plugin** (after `/plugin marketplace add ...` above):

```
/plugin install weftly-setup-dev@weftly
```

**3. Run setup with your testnet wallet name:**

```
/weftly-setup-dev:weftly-setup-dev --wallet <your-testnet-wallet>
```

#### What `/weftly-setup-dev:weftly-setup-dev` does

Mirrors the prod plugin's flow but with three substantive differences:

1. **Asserts mppx ≥ 0.6.7.** The chain-routing fix lands in 0.6.7; below that, testnet challenges silently sign on mainnet.
2. **Registers `weftly` MCP at `https://api.dev.weftly.ai/mcp`** instead of `https://api.weftly.ai/mcp`.
3. **Smoke-tests dev** by hitting `/api/test` ($0.01 testnet PathUSD) with the working incantation (`--rpc-url https://rpc.moderato.tempo.xyz`, `--method-opt mode=push`) so you confirm the whole stack — wallet, mppx, MCP transport, dev MPP middleware — before any real-shaped paid call.

> Heads-up: Claude Code holds one MCP server per name. Running this plugin replaces any prior prod `weftly` registration; rerun `/weftly-setup:weftly-setup` to switch back. We're considering scoped names (`weftly` vs `weftly-dev`) once we have a real cross-env testing workflow.

### `weftly-editing`

Editing skills that orchestrate Weftly transcription and run downstream cleanup on the resulting word-level transcripts. Built on top of `weftly-setup` — install that one first.

**Prerequisites** (in addition to whatever `weftly-setup` already gave you):

- **Python 3.10+** — `remove_fillers.py` is stdlib-only Python. 3.10 is the oldest currently-supported Python and ships by default on Ubuntu 22.04 LTS, Debian 12, current macOS Homebrew, and RHEL/Rocky 9.
- **`curl`** — used by `/weftly-editing:transcribe` to PUT files to Weftly's presigned upload URLs. Pre-installed on virtually every macOS / Linux system.

**1. Install the plugin** (after `weftly-setup` is installed and you've restarted Claude Code):

```
/plugin install weftly-editing@weftly
```

**2. Use the skills.** All editing skills consume Weftly's word-level v2 JSON (`weftly-transcript-v2`) as their canonical input format; SRT is produced as a sibling for tools that need it.

| Skill | What it does |
|-------|--------------|
| `/weftly-editing:transcribe <file>` | Pay, upload, poll, and download. Writes `<base>.words.json` and `<base>.srt` next to the input file. |
| `/weftly-editing:remove-fillers <words.json>` | Remove filler words and false starts from a word-level transcript, using a configurable gap-threshold heuristic. Writes `<base>_cleaned.words.json` and `<base>_cleaned.srt`. |
| `/weftly-editing:transcribe-and-remove-fillers <file>` | Bundled: transcribe → remove-fillers in one shot. |

**Data retention:** files you upload to Weftly and the transcripts it produces are retained for up to 24 hours and then deleted. Download anything you want to keep — these skills always write the transcripts to disk next to your input file. See [weftly.ai](https://weftly.ai) for the privacy policy and terms of service.

## How payments work

Weftly speaks the [Machine Payments Protocol (MPP)](https://mpp.dev). Every paid tool call consumes a small amount of USDC from your mppx wallet — $0.50 for audio transcription, $1.00 for video, etc. (see [pricing](https://weftly.ai)). The wallet and signing happen entirely on your machine; Weftly never sees your key.

Because mppx's own skills teach Claude the payment dance, you do not need a new skill for each Weftly service. New tools ship in the Weftly MCP server, your Claude picks them up on restart, payments just work.

## Pricing

Current Weftly pricing (in USDC):

| Tool | Audio | Video |
|------|------:|------:|
| `transcribe` | $0.50 | $1.00 |
| `summarize`  | $0.75 | $1.25 |

Canonical prices are served by the Weftly MCP server at `tools/list` time — the table above is a snapshot. See [weftly.ai](https://weftly.ai) for the latest.

## Support

- Weftly product questions: [weftly.ai](https://weftly.ai)
- mppx / MPP protocol: [mpp.dev](https://mpp.dev)
- Bugs or feature requests for plugins in this repo: [file an issue](https://github.com/woven-record-media/weftly-plugins/issues)

## License

[MIT](./LICENSE) © Woven Record Media
