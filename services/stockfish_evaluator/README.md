# Stockfish Evaluator

Small HTTP wrapper for Stockfish used by PixelDarts Chess.

```bash
docker build -t ghcr.io/feocco/dartsnut-widgets-stockfish-evaluator:latest services/stockfish_evaluator
docker run --rm -p 8096:8096 ghcr.io/feocco/dartsnut-widgets-stockfish-evaluator:latest
```

## Configuration

Environment variables:

- `SERVICE_HOST`: bind address, default `0.0.0.0`.
- `SERVICE_PORT`: HTTP port, default `8096`.
- `STOCKFISH_PATH`: Stockfish binary path, default `/usr/games/stockfish`.
- `STOCKFISH_DEPTH`: default search depth, default `8`.
- `STOCKFISH_MOVETIME_MS`: default per-position time cap, default `80`.

## Endpoints

### `GET /health`

Starts Stockfish if needed and returns service health:

```json
{"ok": true, "engine": "stockfish"}
```

### `POST /analyse`

Returns the top requested principal-variation heads from one shared search.

Request body:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "depth": 8,
  "movetime_ms": 80,
  "multipv": 8
}
```

Fields:

- `fen` is required. It is the full board state as a FEN string, including
  side to move, castling rights, en-passant target, halfmove clock, and move
  number.
- `depth` is optional. It overrides `STOCKFISH_DEPTH` for this request.
- `movetime_ms` is optional. It overrides `STOCKFISH_MOVETIME_MS` for this
  request.
- `multipv` is optional and defaults to `1`.

Example:

```bash
curl -s http://localhost:8096/analyse \
  -H 'Content-Type: application/json' \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "depth": 8,
    "movetime_ms": 80,
    "multipv": 8
  }'
```

Response body:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "root_score_cp": 31,
  "white_expectation": 0.53,
  "multipv": 8,
  "pvs": [
    {
      "multipv": 1,
      "uci": "e2e4",
      "san": "e4",
      "score_cp_stm": 38,
      "mate": null,
      "white_expectation": 0.54
    }
  ]
}
```

`score_cp_stm` is from the active player's perspective, so
higher means better for the player whose turn it was in the submitted FEN.
`root_score_cp` and `white_expectation` describe the submitted position from
White's perspective. Each PV also includes its resulting White expectation.
The endpoint performs one `engine.analyse(..., multipv=N)` call, not one search
per legal move.

## Depth And Difficulty

`depth` is not an Elo setting. It is a search limit: roughly, how many plies
half-moves Stockfish is allowed to look ahead. `movetime_ms` is also enforced,
so very busy positions may stop because the time limit is reached before the
requested depth is fully searched.

The default `depth=8` and `movetime_ms=80` are chosen for arcade responsiveness,
not master-level analysis. They are strong enough to catch obvious blunders,
captures, checks, and many short tactics for casual players, while keeping a
full legal-move ranking fast enough for a dart game. For this game, that is a
better fit than trying to mimic a 300, 1000, or 1500 Elo player.

If we later add a single-player computer opponent, use Stockfish strength
controls such as `UCI_LimitStrength`/`UCI_Elo` or `Skill Level`. For ranking
human dart choices, keep the evaluator reasonably strong and adjust the target
selection rules instead.
