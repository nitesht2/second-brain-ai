RESULT: EGRESS_BLOCKED

# Geeks of Finance transcript fetch — failure report

Attempted: 2026-08-12 ~18:41–18:47 UTC, from the Claude Code remote session on
branch `claude/geeksoffinance-transcripts`.

## What happened

Egress to youtube.com is blocked by the environment's network-policy proxy.
Every HTTPS CONNECT to YouTube is rejected by the agent-proxy gateway with a
403 before any request reaches YouTube, so no video listing or caption fetch
was possible. Zero transcripts were fetched.

## Exact curl output

```
$ curl -s -o /dev/null -w "%{http_code}" --max-time 15 https://www.youtube.com/
curl: (56) CONNECT tunnel failed, response 403
http_code=000
exit=56
```

Same result for `youtube.com` and `m.youtube.com`.

## Proxy diagnostics

`$HTTPS_PROXY/__agentproxy/status` reports for each attempt:

```
"kind": "connect_rejected",
"detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
"host": "www.youtube.com:443"
```

Retried every 30 s for ~5 minutes (10 attempts, 18:42:12–18:46:46 UTC) to
allow for network-policy propagation; all attempts returned the same 403
CONNECT rejection. The policy update allowing youtube.com has not taken
effect in this environment (or was applied to a different environment).

## What's needed to retry

Add `youtube.com` (and subdomains: `www.youtube.com`, `m.youtube.com`, plus
`*.googlevideo.com` if audio download/whisper fallback is ever wanted) to the
environment's network allowlist, then re-run this fetch task. Tooling is
otherwise ready: `youtube-transcript-api` and `yt-dlp` install fine from PyPI
(PyPI bypasses the proxy), and `deploy/vps/clip_yt_channel.py` works as the
fetcher once egress is open.
