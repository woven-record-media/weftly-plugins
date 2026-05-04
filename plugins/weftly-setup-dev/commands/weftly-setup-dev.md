---
description: Dev-mode setup for Weftly MCP + mppx wallet payments. Points at api.dev.weftly.ai and Tempo Moderato testnet. Requires --wallet <name>.
---

Set up this Claude Code project to call the **dev** Weftly MCP server (`api.dev.weftly.ai`) with automatic MPP payments from a **testnet** mppx wallet on Tempo Moderato (chain 42431).

> Use this plugin when you are testing dev features against a fake-money wallet. It is **not** for production. Funded testnet PathUSD has no real-world value. The prod equivalent (`/weftly-setup:weftly-setup`) registers `api.weftly.ai` and assumes a mainnet-funded wallet.

Flags (parsed from user input): `$ARGUMENTS`

- **`--wallet <name>` / `-w <name>` (required)** — the mppx wallet to use. Must already exist in the local mppx keychain and hold testnet PathUSD on Tempo Moderato (chain 42431). If not present, stop immediately and tell the user:

  > `/weftly-setup-dev:weftly-setup-dev` requires a wallet name. Run:
  > `/weftly-setup-dev:weftly-setup-dev --wallet <name>`
  >
  > Use the name of the testnet mppx wallet you want Claude to pay from. `npx --yes mppx@^0.6.7 account list` shows all wallets on this machine. The wallet must hold **testnet** PathUSD; mainnet USDC is ignored on dev.

  Do not guess, do not default.

Throughout the steps below, substitute `<WALLET>` with the value passed to `--wallet`.

## 1. Verify `npx` is available

Run `command -v npx`.

- If not found: tell the user to install Node.js, then rerun. Stop here.
- If found: run `npx --yes mppx@^0.6.7 --version`. Require **0.6.7 or later** — earlier versions have a chain-routing bug where testnet challenges (chain 42431) get sent to mainnet (chain 4217). If older, tell the user:

  > mppx 0.6.7 or later is required for dev/testnet. Earlier versions silently route testnet challenges to mainnet. Upgrade with:
  > ```
  > npx clear-npx-cache
  > npx --yes mppx@latest --version
  > ```
  > Then rerun `/weftly-setup-dev:weftly-setup-dev --wallet <WALLET>`.

  Stop here.

## 2. Verify the `<WALLET>` wallet exists and is funded on testnet

Run `npx --yes mppx@^0.6.7 account view --account <WALLET>`.

- If the command errors (wallet not found): stop and print:

  > The `<WALLET>` wallet was not found in the mppx keychain. Create one with:
  > ```
  > npx --yes mppx@^0.6.7 account create
  > ```
  > Enter `<WALLET>` at the name prompt, then fund it with testnet PathUSD on Tempo Moderato (chain 42431) — the dev faucet is at https://moderato.tempo.xyz/faucet, or ask in #weftly-dev.
  >
  > Then rerun `/weftly-setup-dev:weftly-setup-dev --wallet <WALLET>`.

- Inspect the output's `balances` array. If there is no entry containing `(testnet)` with a non-zero amount (e.g. `999.5 PathUSD (testnet)`), stop and print the same funding instructions.

- Otherwise, surface the address and the testnet balance verbatim so the user can confirm before paying.

## 3. Set `<WALLET>` as the default account

Run `npx --yes mppx@^0.6.7 account default --account <WALLET>`. Surface any error.

## 4. Register mppx `--mcp` with Claude Code

```bash
claude mcp remove mppx -s user 2>/dev/null || true
claude mcp add -s user mppx -- npx --yes mppx@^0.6.7 --mcp
```

Verify with `claude mcp list | grep mppx` — should show `mppx` pointing at `npx --yes mppx@^0.6.7 --mcp`.

## 5. Sync mppx's bundled skills

Run `npx --yes mppx@^0.6.7 skills add`. This installs `mppx-sign.md` into `~/.claude/skills/` so Claude knows to call the `mppx:sign` tool on `payment_required` errors.

## 6. Register the **dev** Weftly MCP server

```bash
claude mcp remove weftly -s user 2>/dev/null || true
claude mcp add -s user --transport http weftly https://api.dev.weftly.ai/mcp
```

Verify with `claude mcp list | grep weftly` — should show `weftly` pointing at `https://api.dev.weftly.ai/mcp` (note the **dev** subdomain).

> **Heads-up:** Claude Code can only have one MCP server registered at a given name. If `/weftly-setup:weftly-setup` (prod) was previously run on this machine, this step replaces the prod registration with dev. To switch back to prod, run `/weftly-setup:weftly-setup --wallet <prod-wallet>` again.

## 7. Smoke-test the dev plumbing

Run an MPP smoke test against the dev MPP middleware (costs **$0.01 testnet PathUSD**):

```bash
npx --yes mppx@^0.6.7 'https://api.dev.weftly.ai/api/test' \
  --account <WALLET> \
  --rpc-url 'https://rpc.moderato.tempo.xyz' \
  --method-opt mode=push
```

Expected output: HTTP 200 with `{"paid":true,...}`. If you see any other response, stop and surface the failure to the user before proceeding to paid-call testing.

> The `--rpc-url` and `--method-opt mode=push` flags are needed because mppx's own defaults target Tempo mainnet and `pull` mode, which the dev API rejects. mppx 0.6.7+ should infer these from the challenge's chainId — if a future test confirms that, this step can be simplified.

## 8. Print next steps

Tell the user, in plain text:

1. **Restart Claude Code** — new MCP servers and skills only load on a fresh session.
2. After restart, verify `mppx:sign`, `weftly:transcribe`, `weftly:find_clips`, `weftly:extract_clip`, `weftly:extract_vertical_clip` appear in the available tool list.
3. Try a paid call against dev, e.g.: *"find clips from ./sample.mp4 using Weftly"*. Claude should handle the `payment_required` → `mppx:sign` → retry loop automatically using your testnet wallet.
4. Costs on dev are pulled from the same wallet's testnet PathUSD balance; **no real money moves**.

## Notes

- **Dev vs prod isolation.** This plugin only ever points at `api.dev.weftly.ai` and assumes the wallet has testnet PathUSD. The prod plugin (`/weftly-setup:weftly-setup`) only ever points at `api.weftly.ai` and assumes mainnet USDC. Don't try to mix them — Claude Code's MCP registry holds one `weftly` entry at a time.
- **Why `mode=push`.** mppx defaults to `mode=pull` (server broadcasts the signed tx), which the dev API does not currently support. Forcing `mode=push` (client broadcasts, sends the tx hash) is what works today. If the API later advertises `supportedModes` in its challenge, mppx can pick automatically and step 7's flag becomes optional.
- **Why explicit `--rpc-url`.** mppx versions before 0.6.7 ignored the challenge's `chainId: 42431` and tried to send the tx on chain 4217 (Tempo Mainnet), failing with insufficient balance. Pin the RPC to the testnet endpoint to avoid the regression on older mppx builds. From 0.6.7 onward this should be unnecessary; verify in step 1 and remove the flag from local scripts once confirmed.
- **No automatic wallet creation.** Even on testnet, auto-creating a same-named wallet would silently divert payments to a brand-new empty account. Always require the user to confirm the wallet name they want to use.
