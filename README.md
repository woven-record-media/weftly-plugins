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
4. Registers `mppx --mcp` as a local stdio MCP server in Claude Code (`npx mppx mcp add --agent claude-code`).
5. Syncs mppx's bundled skills into `~/.claude/skills/` so Claude knows to call `mppx:sign` on `payment_required` errors (`npx mppx skills add`).
6. Adds a `weftly` entry to the project's `.mcp.json` pointing at the Weftly MCP server.
7. Prints your wallet balance.
8. Prompts you to restart Claude Code.

After restart, Claude Code gains:

- `weftly:transcribe`, `weftly:summarize`, `weftly:complete_upload`, `weftly:get_job_status` (and any future Weftly tools) from the remote HTTP MCP server.
- `mppx:sign`, `mppx:account-*`, etc. from the local stdio MCP server.

When Claude calls a paid Weftly tool, the flow is fully automatic: Weftly returns `payment_required` with a challenge → Claude calls `mppx:sign` (signed against your wallet) → Claude retries the Weftly call with the credential → the tool proceeds.

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
