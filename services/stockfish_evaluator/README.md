# Stockfish Evaluator

Small HTTP wrapper for Stockfish used by PixelDarts Chess.

```bash
docker build -t ghcr.io/feocco/dartsnut-widgets-stockfish-evaluator:latest services/stockfish_evaluator
docker run --rm -p 8096:8096 ghcr.io/feocco/dartsnut-widgets-stockfish-evaluator:latest
```

Endpoints:

- `GET /health`
- `POST /rank` with `{"fen":"...", "depth":8, "movetime_ms":80}`
