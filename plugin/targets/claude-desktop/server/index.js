#!/usr/bin/env node
'use strict'

/**
 * SellerClaw MCP bridge for Claude Desktop — stdio in, hosted MCP out.
 *
 * Why a bridge and not the CLI
 * ---------------------------
 * The bundle used to launch the published Python CLI through `uvx`. That made the extension
 * uninstallable for anyone without a Python toolchain: Claude Desktop refuses to install an
 * extension whose manifest declares a Python runtime when no system Python is found (and even past
 * that gate, `uvx` had to be on PATH). Node.js, by contrast, ships *inside* Claude Desktop — so a
 * Node entry point installs and runs with nothing preinstalled at all.
 *
 * Rather than port ~250 commands to JavaScript, this file forwards MCP traffic to the hosted
 * SellerClaw MCP server (the same Python implementation, deployed once). The tool list, every
 * schema and every error text keep coming from there, so the bundle can never go stale and there is
 * no second implementation to keep in sync. The server is stateless (each POST is self-contained,
 * no session handshake, no session id), which is what lets the bridge stay this thin.
 *
 * What is *not* pure forwarding, and why:
 *   1. `initialize` is answered locally when we have no token. The hosted server requires a bearer
 *      on every request including `initialize`, so a fresh install with no credentials would fail
 *      the handshake and show up as a broken extension — with no way to sign in from inside Claude.
 *   2. `sellerclaw_login` is a local tool implementing the same browser device flow as
 *      `sellerclaw auth login`, writing the same `~/.config/sellerclaw/config.toml`. Without it the
 *      only way to authenticate would be a terminal — the very thing this rewrite removes.
 *
 * stdout carries the MCP protocol and nothing else; diagnostics go to stderr.
 */

const fs = require('node:fs')
const http = require('node:http')
const https = require('node:https')
const os = require('node:os')
const path = require('node:path')
const { spawn } = require('node:child_process')

const DEFAULT_MCP_URL = 'https://mcp.sellerclaw.ai/mcp'
const DEFAULT_API_URL = 'https://api.sellerclaw.ai'
const SERVER_NAME = 'sellerclaw'
const FALLBACK_PROTOCOL_VERSION = '2025-06-18'

// A tool call may legitimately run for minutes (publishing a listing, a research sweep), so the
// socket budget is generous; it exists only so a dead connection cannot wedge a request forever.
const FORWARD_TIMEOUT_MS = 15 * 60 * 1000
// The handshake must not stall startup — if the hosted server is unreachable we answer locally.
const INITIALIZE_TIMEOUT_MS = 10_000
// The tool list gets a longer budget than the handshake: failing it is not a graceful degradation
// (the user would see an empty SellerClaw and think they were signed out), and the hosted machine
// may be cold-starting.
const TOOLS_LIST_TIMEOUT_MS = 30_000
const AUTH_CALL_TIMEOUT_MS = 20_000
// How long one `sellerclaw_login` call waits for the human before returning "still waiting". Kept
// well under a client's tool-call timeout: the flow resumes on the next call, nothing is lost.
// Overridable so the test suite does not have to sit through a real waiting window.
const LOGIN_POLL_BUDGET_MS = Number(process.env.SELLERCLAW_LOGIN_POLL_MS) > 0
  ? Number(process.env.SELLERCLAW_LOGIN_POLL_MS)
  : 50_000

const MCP_URL = (process.env.SELLERCLAW_MCP_URL || '').trim() || DEFAULT_MCP_URL

// Who is signing in, sent with the sign-in calls. `cli` is the interactive class — a person is in
// Claude Desktop for every turn — which is what lets them answer a SellerClaw approval right here
// instead of only in the web app; the name is what SellerClaw shows next to anything approved this
// way. A sign-in that says nothing is treated as an unattended agent, the strictest case.
const CLIENT_IDENTITY = {
  'X-Client-Kind': 'cli',
  'X-Client-Name': 'SellerClaw for Claude Desktop',
}

const LOGIN_TOOL = {
  name: 'sellerclaw_login',
  description:
    'Sign in to SellerClaw. Opens the browser so the account owner can approve access — no token '
    + 'to copy and nothing to install. Call this when a SellerClaw command fails because the user '
    + 'is not signed in, and call it again after they approve if it reports it is still waiting.',
  inputSchema: { type: 'object', properties: {}, additionalProperties: false },
}

// Used only when we answer `initialize` ourselves (no token yet, or the server is unreachable). The
// real instructions come from the hosted server the moment it answers, so this stays deliberately
// short — a second copy of them here would drift.
const FALLBACK_INSTRUCTIONS =
  'SellerClaw e-commerce control over the seller\'s stores, orders, listings, ads, suppliers, email '
  + 'and research. This connection is not signed in yet: call the `sellerclaw_login` tool to open '
  + 'the browser and approve access — after that the full SellerClaw command surface appears.'

const NOT_SIGNED_IN_MESSAGE =
  'Not signed in to SellerClaw (no token, or the saved one is no longer valid). Call the '
  + '`sellerclaw_login` tool — it opens the browser to approve access; nothing to install.'

// --------------------------------------------------------------------------------------------- //
// Config file — the same one `sellerclaw auth login` writes, so a user who already signed in from a
// terminal is signed in here too, and a sign-in here counts for the CLI.

function configPath() {
  const xdg = (process.env.XDG_CONFIG_HOME || '').trim()
  const base = xdg || path.join(os.homedir(), '.config')
  return path.join(base, 'sellerclaw', 'config.toml')
}

/** Read one top-level string key out of config.toml. Deliberately not a TOML parser: the file only
 *  ever holds flat `key = "value"` scalars, and a dependency here would mean bundling node_modules. */
function readConfigValue(key) {
  let text
  try {
    text = fs.readFileSync(configPath(), 'utf8')
  } catch {
    return null
  }
  const match = text.match(new RegExp(`^\\s*${key}\\s*=\\s*"([^"]*)"\\s*$`, 'm'))
  return match ? match[1] : null
}

/** Persist the token, preserving every other line verbatim (api_url and anything a newer CLI adds). */
function saveToken(token) {
  const file = configPath()
  let text = ''
  try {
    text = fs.readFileSync(file, 'utf8')
  } catch {
    text = ''
  }
  const line = `token = ${JSON.stringify(token)}`
  if (/^\s*token\s*=.*$/m.test(text)) {
    text = text.replace(/^\s*token\s*=.*$/m, line)
  } else {
    text = text.length && !text.endsWith('\n') ? `${text}\n${line}\n` : `${text}${line}\n`
  }
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, text, { mode: 0o600 })
  try {
    fs.chmodSync(file, 0o600)
  } catch {
    // Non-POSIX filesystems may reject chmod — the CLI makes the same allowance.
  }
}

function apiUrl() {
  return (process.env.SELLERCLAW_API_URL || '').trim() || readConfigValue('api_url') || DEFAULT_API_URL
}

/** Env wins over the config file, matching the CLI's own precedence. An empty user_config field
 *  arrives as an empty string, which must read as "not set" rather than as an empty token — and a
 *  host that failed to substitute the field hands us the raw `${user_config.token}` placeholder,
 *  which must not shadow a real signed-in session in the config file. */
function loadToken() {
  const fromEnv = (process.env.SELLERCLAW_TOKEN || '').trim()
  if (fromEnv && !fromEnv.includes('${')) return fromEnv
  const fromFile = (readConfigValue('token') || '').trim()
  return fromFile || null
}

let token = loadToken()

function bundleVersion() {
  try {
    return JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'manifest.json'), 'utf8')).version
  } catch {
    return '0.0.0'
  }
}

// --------------------------------------------------------------------------------------------- //
// HTTP

/**
 * One HTTP round trip, fully buffered.
 *
 * `onRequest` hands the live request object back to the caller so an in-flight call can be aborted
 * when the client cancels it.
 */
function httpRequest(urlString, { method = 'POST', headers = {}, body = null, timeoutMs = 0, onRequest } = {}) {
  return new Promise((resolve, reject) => {
    let url
    try {
      url = new URL(urlString)
    } catch (err) {
      reject(err)
      return
    }
    const transport = url.protocol === 'http:' ? http : https
    const payload = body == null ? null : Buffer.from(JSON.stringify(body), 'utf8')
    const finalHeaders = { ...headers }
    if (payload) {
      finalHeaders['Content-Type'] = 'application/json'
      finalHeaders['Content-Length'] = String(payload.length)
    }
    const req = transport.request(url, { method, headers: finalHeaders }, (res) => {
      const chunks = []
      res.on('data', (chunk) => chunks.push(chunk))
      res.on('end', () => {
        resolve({
          status: res.statusCode || 0,
          headers: res.headers,
          text: Buffer.concat(chunks).toString('utf8'),
        })
      })
    })
    req.on('error', reject)
    if (timeoutMs > 0) {
      req.setTimeout(timeoutMs, () => req.destroy(new Error(`timed out after ${timeoutMs}ms`)))
    }
    if (onRequest) onRequest(req)
    if (payload) req.write(payload)
    req.end()
  })
}

/** Parse a response body into JSON-RPC messages. The hosted server answers `text/event-stream`
 *  (one `data:` line per message), but plain JSON is accepted too so a different deployment or a
 *  proxy that collapses the stream still works. */
function parseMessages(response) {
  const contentType = String(response.headers['content-type'] || '')
  const text = response.text.trim()
  if (!text) return []
  if (contentType.includes('text/event-stream')) {
    const messages = []
    for (const line of response.text.split(/\r?\n/)) {
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (!data || data === '[DONE]') continue
      try {
        messages.push(JSON.parse(data))
      } catch {
        // A malformed frame is not worth killing the connection over; skip it.
      }
    }
    return messages
  }
  try {
    const parsed = JSON.parse(text)
    return Array.isArray(parsed) ? parsed : [parsed]
  } catch {
    return []
  }
}

class UpstreamError extends Error {
  constructor(message, { status = 0, unauthorized = false } = {}) {
    super(message)
    this.status = status
    this.unauthorized = unauthorized
  }
}

/** Send one JSON-RPC message upstream and return every message that came back. */
async function callUpstream(message, { timeoutMs = FORWARD_TIMEOUT_MS, onRequest } = {}) {
  const headers = {
    Accept: 'application/json, text/event-stream',
    'MCP-Protocol-Version': negotiatedProtocolVersion,
  }
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await httpRequest(MCP_URL, { headers, body: message, timeoutMs, onRequest })
  } catch (err) {
    throw new UpstreamError(
      `Could not reach the SellerClaw MCP server at ${MCP_URL}: ${err.message}. `
      + 'Check the internet connection and try again.',
    )
  }
  if (response.status === 401 || response.status === 403) {
    throw new UpstreamError(NOT_SIGNED_IN_MESSAGE, { status: response.status, unauthorized: true })
  }
  if (response.status >= 400) {
    throw new UpstreamError(
      `SellerClaw MCP server returned HTTP ${response.status}: ${response.text.slice(0, 400)}`,
      { status: response.status },
    )
  }
  return parseMessages(response)
}

// --------------------------------------------------------------------------------------------- //
// stdio plumbing

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`)
}

function sendResult(id, result) {
  send({ jsonrpc: '2.0', id, result })
}

function sendError(id, code, message) {
  send({ jsonrpc: '2.0', id, error: { code, message } })
}

/** A failed `tools/call` is reported as an error *result* rather than a JSON-RPC error: the model
 *  sees the text and can act on it (e.g. call `sellerclaw_login`) instead of the client swallowing
 *  a transport-level failure. Every other method uses a proper JSON-RPC error. */
function sendFailure(message, text, { code = -32603 } = {}) {
  if (message.method === 'tools/call') {
    sendResult(message.id, { content: [{ type: 'text', text }], isError: true })
    return
  }
  sendError(message.id, code, text)
}

let negotiatedProtocolVersion = FALLBACK_PROTOCOL_VERSION
const inFlight = new Map()
// Requests the client took back. A cancelled request must not get a response, so the abort that
// follows must not be reported as a failure either.
const cancelled = new Set()

// --------------------------------------------------------------------------------------------- //
// Device-flow sign-in (mirrors `sellerclaw auth login`)

/** The device code currently awaiting approval, so a second `sellerclaw_login` call resumes the
 *  same flow instead of invalidating the code the user is looking at. */
let pendingDevice = null

async function apiPost(pathname, body) {
  const response = await httpRequest(`${apiUrl().replace(/\/+$/, '')}${pathname}`, {
    method: 'POST',
    headers: { Accept: 'application/json', ...CLIENT_IDENTITY },
    body: body || {},
    timeoutMs: AUTH_CALL_TIMEOUT_MS,
  })
  let parsed = null
  try {
    parsed = JSON.parse(response.text)
  } catch {
    parsed = null
  }
  return { status: response.status, body: parsed, text: response.text }
}

async function apiGet(pathname, bearer) {
  const response = await httpRequest(`${apiUrl().replace(/\/+$/, '')}${pathname}`, {
    method: 'GET',
    headers: { Accept: 'application/json', Authorization: `Bearer ${bearer}` },
    timeoutMs: AUTH_CALL_TIMEOUT_MS,
  })
  let parsed = null
  try {
    parsed = JSON.parse(response.text)
  } catch {
    parsed = null
  }
  return { status: response.status, body: parsed }
}

function openBrowser(url) {
  if ((process.env.SELLERCLAW_NO_BROWSER || '').trim()) return
  const [command, args] = process.platform === 'darwin'
    ? ['open', [url]]
    : process.platform === 'win32'
      ? ['cmd', ['/c', 'start', '', url]]
      : ['xdg-open', [url]]
  try {
    const child = spawn(command, args, { stdio: 'ignore', detached: true })
    child.on('error', () => {})
    child.unref()
  } catch {
    // No browser opener available (headless box) — the tool result still carries the URL and code.
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function loginText(device, extra) {
  return `${extra}\n\nOpen ${device.verificationUri} and enter the code ${device.userCode}.`
}

async function startDeviceFlow() {
  const response = await apiPost('/agent/auth/device/code', {})
  const body = response.body
  if (response.status >= 400 || !body || !body.device_code) {
    throw new Error(
      `SellerClaw could not start the sign-in (HTTP ${response.status}). Try again in a moment.`,
    )
  }
  return {
    deviceCode: String(body.device_code),
    userCode: String(body.user_code || ''),
    verificationUri: String(body.verification_uri || ''),
    intervalMs: Math.max(1, Number(body.interval) || 5) * 1000,
    expiresAt: Date.now() + (Number(body.expires_in) || 600) * 1000,
  }
}

/** Poll until the owner approves, the budget runs out, or the flow fails. Returns the token, or
 *  null when the answer is simply "not yet" — the caller then asks the user to come back. */
async function pollDeviceToken(device, budgetMs) {
  const deadline = Date.now() + budgetMs
  let intervalMs = device.intervalMs
  while (Date.now() < deadline) {
    if (Date.now() >= device.expiresAt) {
      throw new Error('The sign-in code expired before it was approved. Call `sellerclaw_login` again.')
    }
    const response = await apiPost('/agent/auth/device/token', { device_code: device.deviceCode })
    const body = response.body || {}
    if (typeof body.agent_token === 'string' && body.agent_token) return body.agent_token
    const error = body.error
    if (error === 'slow_down') {
      intervalMs += 5000
    } else if (error && error !== 'authorization_pending') {
      throw new Error(`SellerClaw sign-in failed: ${error}. Call \`sellerclaw_login\` to start over.`)
    }
    await sleep(intervalMs)
  }
  return null
}

async function handleLogin(message) {
  // Already holding a working token? Say who it belongs to rather than pointlessly re-authorizing.
  if (token) {
    try {
      const me = await apiGet('/agent/me', token)
      if (me.status === 200) {
        const name = me.body && me.body.name ? ` as ${me.body.name}` : ''
        sendResult(message.id, {
          content: [{ type: 'text', text: `Already signed in to SellerClaw${name}. Nothing to do.` }],
          isError: false,
        })
        return
      }
    } catch {
      // Unreachable API — fall through and let the device flow report the real problem.
    }
  }

  try {
    if (!pendingDevice || Date.now() >= pendingDevice.expiresAt) {
      pendingDevice = await startDeviceFlow()
      openBrowser(pendingDevice.verificationUri)
    }
    const device = pendingDevice
    const granted = await pollDeviceToken(device, LOGIN_POLL_BUDGET_MS)
    if (!granted) {
      sendResult(message.id, {
        content: [{
          type: 'text',
          text: loginText(
            device,
            'Still waiting for the SellerClaw sign-in to be approved in the browser. Approve it, '
            + 'then call `sellerclaw_login` again — the same code stays valid.',
          ),
        }],
        isError: false,
      })
      return
    }
    pendingDevice = null
    token = granted
    saveToken(granted)
    // The tool list was just the login tool while unauthenticated; tell the client to re-read it so
    // the real SellerClaw tools appear without restarting Claude.
    send({ jsonrpc: '2.0', method: 'notifications/tools/list_changed' })
    sendResult(message.id, {
      content: [{
        type: 'text',
        text: 'Signed in to SellerClaw. The SellerClaw tools are available now — retry what you were doing.',
      }],
      isError: false,
    })
  } catch (err) {
    pendingDevice = null
    sendResult(message.id, {
      content: [{ type: 'text', text: err.message }],
      isError: true,
    })
  }
}

// --------------------------------------------------------------------------------------------- //
// MCP methods

async function handleInitialize(message) {
  const requested = message.params && typeof message.params.protocolVersion === 'string'
    ? message.params.protocolVersion
    : FALLBACK_PROTOCOL_VERSION
  negotiatedProtocolVersion = requested

  if (token) {
    try {
      const replies = await callUpstream(message, { timeoutMs: INITIALIZE_TIMEOUT_MS })
      const reply = replies.find((m) => m && m.result && m.id === message.id)
      if (reply) {
        if (typeof reply.result.protocolVersion === 'string') {
          negotiatedProtocolVersion = reply.result.protocolVersion
        }
        // Force listChanged on: the tool list changes locally the moment a sign-in succeeds, and
        // the client only re-reads it if the server said it might.
        const capabilities = reply.result.capabilities || {}
        reply.result.capabilities = { ...capabilities, tools: { ...(capabilities.tools || {}), listChanged: true } }
        send(reply)
        return
      }
    } catch (err) {
      process.stderr.write(`sellerclaw: handshake with ${MCP_URL} failed (${err.message}); continuing locally\n`)
    }
  }

  sendResult(message.id, {
    protocolVersion: requested,
    capabilities: { tools: { listChanged: true } },
    serverInfo: { name: SERVER_NAME, version: bundleVersion() },
    instructions: FALLBACK_INSTRUCTIONS,
  })
}

async function handleToolsList(message) {
  if (!token) {
    sendResult(message.id, { tools: [LOGIN_TOOL] })
    return
  }
  try {
    const replies = await callUpstream(message, { timeoutMs: TOOLS_LIST_TIMEOUT_MS })
    const reply = replies.find((m) => m && m.result && m.id === message.id)
    if (!reply) {
      sendResult(message.id, { tools: [LOGIN_TOOL] })
      return
    }
    const tools = Array.isArray(reply.result.tools) ? reply.result.tools : []
    // Only the last page may carry the extra tool, or a paginating client would see it twice.
    reply.result.tools = reply.result.nextCursor ? tools : [...tools, LOGIN_TOOL]
    send(reply)
  } catch (err) {
    if (err.unauthorized) {
      sendResult(message.id, { tools: [LOGIN_TOOL] })
      return
    }
    sendFailure(message, err.message)
  }
}

async function forward(message) {
  try {
    const replies = await callUpstream(message, {
      onRequest: (req) => inFlight.set(message.id, req),
    })
    if (cancelled.has(message.id)) return
    if (!replies.length) {
      sendFailure(message, `The SellerClaw MCP server returned an empty response for ${message.method}.`)
      return
    }
    for (const reply of replies) send(reply)
  } catch (err) {
    if (!cancelled.has(message.id)) sendFailure(message, err.message)
  } finally {
    inFlight.delete(message.id)
    cancelled.delete(message.id)
  }
}

async function handleRequest(message) {
  switch (message.method) {
    case 'initialize':
      await handleInitialize(message)
      return
    case 'ping':
      sendResult(message.id, {})
      return
    case 'tools/list':
      await handleToolsList(message)
      return
    case 'tools/call':
      if (message.params && message.params.name === LOGIN_TOOL.name) {
        await handleLogin(message)
        return
      }
      if (!token) {
        sendResult(message.id, {
          content: [{ type: 'text', text: NOT_SIGNED_IN_MESSAGE }],
          isError: true,
        })
        return
      }
      await forward(message)
      return
    default:
      await forward(message)
  }
}

function handleNotification(message) {
  if (message.method === 'notifications/cancelled') {
    const id = message.params && message.params.requestId
    const req = inFlight.get(id)
    if (req) {
      cancelled.add(id)
      req.destroy(new Error('cancelled by client'))
      inFlight.delete(id)
    }
    return
  }
  // Everything else (notifications/initialized, logging levels, …) concerns a handshake we answer
  // ourselves; the stateless server has no session to tell about it.
}

function handleMessage(raw) {
  let message
  try {
    message = JSON.parse(raw)
  } catch {
    sendError(null, -32700, 'Parse error: the SellerClaw bridge received invalid JSON.')
    return
  }
  if (!message || typeof message !== 'object' || Array.isArray(message)) return
  if (message.id === undefined || message.id === null) {
    handleNotification(message)
    return
  }
  if (typeof message.method !== 'string') return // a response to something we never asked for
  handleRequest(message).catch((err) => {
    sendFailure(message, `SellerClaw bridge error: ${err && err.message ? err.message : String(err)}`)
  })
}

function main() {
  if (!token) {
    process.stderr.write(
      'sellerclaw: not signed in — ask Claude to run the sellerclaw_login tool, or run '
      + '`sellerclaw auth login` in a terminal.\n',
    )
  }
  let buffer = ''
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', (chunk) => {
    buffer += chunk
    let index = buffer.indexOf('\n')
    while (index !== -1) {
      const line = buffer.slice(0, index).trim()
      buffer = buffer.slice(index + 1)
      if (line) handleMessage(line)
      index = buffer.indexOf('\n')
    }
  })
  process.stdin.on('end', () => process.exit(0))
}

main()
