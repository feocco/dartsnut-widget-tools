# Cloud Agent Tailscale handoff

## Access boundary

Cloud Agent nodes use only `tag:cursor-cloud`. That tag can reach only
`svc:stockfish-evaluator` on TCP 8096. Stockfish keeps its existing LAN listener
for the physical Dartsnut board.

## Tailscale admin checkpoint

Before launching the Cloud Agent:

1. Define `stockfish-evaluator` on the Tailscale Services page with endpoint
   `tcp:8096`.
2. Merge the `tag:cursor-cloud` owner, grant, and policy tests from
   `homelab-config/docs/tailscale-friends-policy.hujson` into the live policy.
   Do not replace the existing policy or add this tag to an owner-wide grant.
3. Deploy `homelab-config` branch
   `cursor/stockfish-tailscale-service-f8ff` as a Mac mini canary.
4. Approve the pending Mac mini advertisement on the service page.
5. Verify the service's MagicDNS URL returns healthy `/health` and `/analyse`
   responses, then merge and redeploy the homelab change from `main`.
6. Save the service base URL as the Cloud Agent environment variable
   `STOCKFISH_URL`.
7. Save the reusable ephemeral key tagged only `tag:cursor-cloud` as the Cloud
   Agent runtime secret `TS_AUTHKEY`.

Never paste either runtime value into a task, terminal command, log, file,
commit, screenshot, or pull request.

## Cloud Agent kickoff prompt

```text
Complete the Cloud runtime verification for the userspace Tailscale PR on this
branch.

1. Confirm TS_AUTHKEY and STOCKFISH_URL are non-empty without printing them.
   Stop if either is missing.
2. Probe https://controlplane.tailscale.com/ and
   https://login.tailscale.com/ with curl -I --max-time 8. Stop on
   SSL_ERROR_SYSCALL.
3. If tailscale or tailscaled is absent, run
   .cursor/scripts/install-tailscale.sh. Request a test Build only if the
   client cannot otherwise be installed from this branch.
4. Run .cursor/scripts/start-tailscale.sh. Verify the userspace status is
   online and the node has only tag:cursor-cloud.
5. Through socks5h://127.0.0.1:1055, verify STOCKFISH_URL/health and one real
   /analyse request.
6. Through the same SOCKS5 proxy, verify the Stockfish service on TCP 443 is
   denied. Confirm the live policy's tests deny the unrelated named services
   and direct tag:homelab-service-host access. Raw direct 100.x curl failure is
   expected and is not ACL proof.
7. Run every AGENTS.md repository check and the relevant PixelDarts Chess
   verification skill.
8. Capture a real terminal screenshot or video showing the triggering commands
   and successful results without exposing either runtime value.
9. If the join succeeds but service traffic hangs, report likely DERP-by-IP
   versus domain-allowlist behavior and stop. Do not add speculative domains.
10. Commit and push necessary corrections. Update the draft PR with minimal
    evidence and mark it ready only after all positive and negative checks pass.
```
