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

1. Verifies `npx` and `mppx >= 0.6.5` are available.
2. Confirms the named wallet exists in your mppx keychain and sets it as the default.
3. Registers the mppx MCP server with Claude Code (user-scoped), which exposes the `mppx:sign` tool Claude needs to satisfy payment challenges.
4. Syncs mppx's bundled skills so Claude knows to call `mppx:sign` automatically when a paid tool returns `payment_required`.
5. Registers the Weftly MCP server with Claude Code (user-scoped), making Weftly tools available in every project after a single setup run.
6. Prints your wallet balance and prompts you to restart Claude Code.

After restart, paid Weftly calls are fully automatic: Weftly returns a payment challenge → Claude signs it with your wallet → the tool proceeds.

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
