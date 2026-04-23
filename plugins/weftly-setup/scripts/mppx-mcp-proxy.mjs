#!/usr/bin/env node
// Lightweight MCP stdio proxy around the `mppx` CLI.
//
// Why this exists: mppx 0.6.3's own `--mcp` mode has two upstream bugs —
//   (1) `bin.js` races `process.exit(0)` before handling any request, and
//   (2) command handlers only `console.log(...)` their output, so every MCP
//       tool returns `null` AND leaks raw output into the JSON-RPC channel,
//       corrupting the stream and dropping the client.
//
// This proxy implements MCP stdio itself and shells out to `npx --yes mppx`
// per call, parsing stdout into structured tool results. Only exposes `sign`
// — that's what Weftly's unattended payment flow needs.

import { spawn } from 'node:child_process';
import readline from 'node:readline';

const PROTOCOL_VERSION = '2025-03-26';
const SERVER_INFO = { name: 'mppx-proxy', version: '0.1.0' };

const TOOLS = [
  {
    name: 'sign',
    description:
      'Sign a payment challenge (a WWW-Authenticate value from a 402 response) using mppx and return an Authorization header value. ' +
      'Use this to satisfy an MPP `payment_required` challenge from any mppx-enabled API.',
    inputSchema: {
      type: 'object',
      properties: {
        challenge: {
          type: 'string',
          description: 'The WWW-Authenticate challenge value (e.g. `Payment id="...", realm="...", method="tempo", ...`).',
        },
        account: {
          type: 'string',
          description: 'Optional mppx account name. Uses the configured default account if omitted.',
        },
        rpc_url: {
          type: 'string',
          description: 'Optional RPC endpoint override (e.g. for testnet). Defaults to the public RPC for the chain.',
        },
      },
      required: ['challenge'],
      additionalProperties: false,
    },
  },
];

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}

function reply(id, result) {
  send({ jsonrpc: '2.0', id, result });
}

function errReply(id, code, message, data) {
  send({ jsonrpc: '2.0', id, error: { code, message, ...(data ? { data } : {}) } });
}

function runSign({ challenge, account, rpc_url }) {
  const args = ['--yes', 'mppx', 'sign', '--challenge', challenge];
  if (account) args.push('--account', account);
  if (rpc_url) args.push('--rpc-url', rpc_url);

  return new Promise((resolve, reject) => {
    const child = spawn('npx', args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      env: process.env,
    });
    let out = '';
    let errOut = '';
    child.stdout.on('data', (c) => { out += c.toString('utf8'); });
    child.stderr.on('data', (c) => { errOut += c.toString('utf8'); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code !== 0) {
        const msg = (errOut.trim() || out.trim() || `mppx sign exited with code ${code}`);
        reject(new Error(msg));
        return;
      }
      const authorization = out.split('\n').find((l) => l.startsWith('Payment '));
      if (!authorization) {
        reject(new Error(`Could not parse mppx sign output: ${out.slice(0, 200)}`));
        return;
      }
      resolve(authorization);
    });
  });
}

async function handleToolCall(name, args) {
  if (name === 'sign') {
    const { challenge, account, rpc_url } = args || {};
    if (!challenge || typeof challenge !== 'string') {
      return {
        content: [{ type: 'text', text: 'Missing required string argument: challenge' }],
        isError: true,
      };
    }
    try {
      const authorization = await runSign({ challenge, account, rpc_url });
      return {
        content: [{ type: 'text', text: JSON.stringify({ authorization }) }],
        structuredContent: { authorization },
      };
    } catch (e) {
      return {
        content: [{ type: 'text', text: e?.message || String(e) }],
        isError: true,
      };
    }
  }
  return {
    content: [{ type: 'text', text: `Unknown tool: ${name}` }],
    isError: true,
  };
}

const pending = new Set();
let stdinClosed = false;

function maybeExit() {
  if (stdinClosed && pending.size === 0) process.exit(0);
}

function track(promise) {
  pending.add(promise);
  promise.finally(() => {
    pending.delete(promise);
    maybeExit();
  });
  return promise;
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on('line', (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  let msg;
  try { msg = JSON.parse(trimmed); } catch { return; }
  const { id, method, params } = msg;
  const handler = async () => {
    try {
      switch (method) {
        case 'initialize':
          reply(id, {
            protocolVersion: PROTOCOL_VERSION,
            capabilities: { tools: { listChanged: false } },
            serverInfo: SERVER_INFO,
          });
          break;
        case 'notifications/initialized':
        case 'notifications/cancelled':
          break;
        case 'tools/list':
          reply(id, { tools: TOOLS });
          break;
        case 'tools/call': {
          const { name, arguments: toolArgs } = params || {};
          const result = await handleToolCall(name, toolArgs);
          reply(id, result);
          break;
        }
        case 'ping':
          reply(id, {});
          break;
        default:
          if (id !== undefined) errReply(id, -32601, `Method not found: ${method}`);
      }
    } catch (e) {
      if (id !== undefined) errReply(id, -32603, e?.message || String(e));
    }
  };
  track(handler());
});

rl.on('close', () => {
  stdinClosed = true;
  maybeExit();
});
