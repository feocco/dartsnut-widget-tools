# Live Stockfish

Prove the deployed evaluator contract and one game continuation against the real HTTP service.

## Sub-features

- `analyse-contract` returns eight unique legal PV heads with scores and White-POV fields.
- `rank-removed` returns `404` from `POST /rank`.
- `single-search` records one UCI `go` command for the direct MultiPV request.
- `live-continuation` records `before_wdl` and `after_wdl` from `HttpStockfishEvaluator`.

## How to get to it (user POV)

- Start the evaluator through its managed Compose service.
- Point `STOCKFISH_API_URL` at that service.
- Complete both players' target turns so the match requests a continuation.

## Driving it with verify_live_stockfish

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/verify_live_stockfish.py \
  --url http://127.0.0.1:8096 \
  --container stockfish-evaluator \
  --out artifacts/goal-5-stockfish
```

Require `summary.json` to report `analyse_status: 200`, `rank_status: 404`,
`multipv: 8`, `unique_uci: 8`, `direct_engine_go_commands: 1`, and
`evaluator: HttpStockfishEvaluator`.

## Gotchas

- Fixture-backed `drive_headless.py` does not prove live Stockfish.
- A successful `/health` response does not prove the `/analyse` contract.
- Counting HTTP requests does not prove engine searches. Count UCI `go` commands.
- Clear `STOCKFISH_PATH` so a failed HTTP call cannot fall through to a local engine.

## Live turn path

Turn choice, side-to-move, and stalled or illegal continuations use a separate hook. It talks to the live HTTP API and then drives `record_gameplay.py` / `main.py`. It does not use MultiPV fixtures.

```bash
bash .cursor/cloud/tailscale-userspace.sh
source .cursor/cloud/tailscale-proxy.env
python3 .cursor/skills/verify-pixeldarts-chess/helpers/verify_live_turn_path.py \
  --out artifacts/verify-pixeldarts-chess/live-turn-path
```

The hook exits `2` when `TAILSCALE_AUTH_KEY` or `STOCKFISH_API_URL` is unset. Do not invent a URL. Fixture mode stays on `drive_headless.py` for changes that do not touch engine replies or continuation state.

`--rounds` defaults to 3. Use `--rounds 5` when checking the window where the physical board was reported to stick. A legal mate before the last requested `board_hold` is a pass, not a stuck side. A 5-round live process drive on current main produced five legal alternating continuations and `Nxf7#` in round 5; it did not reproduce a one-sided or stalled turn.
