# Continuation planner

Notes for replacing dart-picked chess moves with an arcade-score continuation. Forward this to the implementing agent.

## What to build

After each balloon-pop round, the engine plays six half-moves (three full moves). The arcade winner gets an advantage. Show the actual Stockfish win percentages before and after. Players do not pick pieces or moves.

Directionally accurate is enough. Do not try to hit a specific win percentage. A position may not contain a legal line that lands on an arbitrary number.

## Do not extend `/rank`

`POST /rank` in `services/stockfish_evaluator/app.py` evaluates the root, then runs a separate `engine.analyse` for every legal move. A normal middlegame is about 31 analyses. That exists to rank every legal move onto dart wedges.

Do not reuse it for six plies. Naive extension is roughly 190 analyses per round. At the current defaults (`depth=8`, `movetime_ms=80`) a single `/rank` already can take a couple of seconds, and `HttpStockfishEvaluator` times out at 1.5s, then silently falls back to `StaticMaterialEvaluator`. That fallback is junk for this feature.

If dart-picked moves go away, `/rank` is unused by the chess game. Retire it or keep it for the old widget. Decide, do not leave it as the default path.

## The cheap engine trick

One `engine.analyse(board, limit, multipv=N)` returns the top N moves with scores from a shared search. You get the best move and the alternatives in one call.

`multipv=8` costs more than `multipv=1` at the same depth. It is not eight times as expensive. Measure it.

Scores are from the side to move. Candidate loss is `best_score - candidate_score`.

## Algorithm

Six plies. Each player moves three times, whoever is on turn. Decide each ply from the position that actually happened. No tree search.

Winner ply. `multipv=1`. Play the best move.

Loser ply. `multipv=6` to `8`. Play the candidate whose centipawn loss is closest to the band target. If nothing loses that much, take the largest available loss and continue. Do not spend extra calls hunting for a worse move.

That is six engine calls per round. Three cheap, three wider.

Why this works. Each loser ply is scored against a position that already includes the previous loss, so three 100cp hits land near a 300cp swing. The winner's next search already exploits whatever the loser just gave up. You do not need to coordinate the six moves.

Skip "best over the next 3 moves." Stockfish's eval already looks ahead. Greedy best-for-the-winner is close enough. What you lose is aiming at a target percentage, which we already dropped.

## Margin bands

```text
margin = (winner_score - loser_score) / maximum_possible_score
```

Apply the loss only on the loser's three plies.

| Margin | Band | Loser target loss |
|---:|---|---:|
| Tie | balanced | 0cp (both sides best) |
| 1-10% | small | ~40cp |
| 11-25% | clear | ~100cp |
| 26-40% | strong | ~200cp |
| 41%+ | dominant | ~350cp, mate allowed once unlocked |

Starting values, not tuned. `game_state.py` already uses 100/300cp for dart wedges (`GREAT_MAX_LOSS_CP`, `OKAY_MAX_LOSS_CP`, `BLUNDER_MIN_LOSS_CP`). Reuse those numbers if they still fit.

Sudden death should make ties unreachable. Keep the balanced row anyway so the planner never gets an undefined band.

## Checkmate

Rounds 1-3. Reject lines that contain checkmate.

Round 3. Announce that mate is now live.

Round 4 onward. Mate is allowed.

Each candidate's eval already says if it is a mate score. Filter the `MultiPV` list. No extra calls. During locked rounds, skip candidates that deliver mate or hand the opponent a mate score. Skip a winner best-move that mates.

If filtering leaves nothing, play the best non-mating legal move. If every legal move mates, accept it. Truncate early if the position dies mid-sequence for any other reason (stalemate, insufficient material).

## New endpoint

Do not overload `/rank`.

```
POST /continuation
{
  "fen": "...",
  "beneficiary": "white",
  "band": "clear",
  "round_index": 4,
  "plies": 6,
  "depth": 10,
  "movetime_ms": 120,
  "seed": 12345
}
```

Return enough to drive the animation without recomputing. Ordered moves with `uci`, `san`, whose ply it was, the centipawn loss taken, and the eval after that ply. Also return root and final `root_score_cp` and `white_expectation`. Use `wdl(model="sf").expectation()` so the bar matches what the game already shows.

Pass the round seed through. Use it only to break ties among equal candidates so a round is reproducible.

## Client

Reuse the existing analysis plumbing. `PixelDartsChessRuntime` in `chess_game.py` runs analysis on a worker thread, locks the evaluator, and posts `AnalysisCompleted` onto a queue. `game_state.py` already has `RequestAnalysis` plus `ThinkingPhase` with a minimum on-screen wait. A continuation request fits that pattern. Put the tug-of-war meter on screen during the wait.

Raise the HTTP timeout for this endpoint. Six sequential calls at higher depth will blow past 1.5s. The silent material-eval fallback would produce garbage continuations.

## Openings

Keep the current pre-game opening pick. `openings.py` applies a stored eight-ply line from the fixtures. Zero engine calls. Players start from a named opening.

Start arcade rounds after the book line is applied. If round 1 fires while still in book, you either break the book to manufacture an inaccuracy or the round winner sees nothing happen. Apply the book first so those two goals do not collide.

## Implementation order

1. `/continuation` with the greedy planner and the mate gate.
2. Unit-test candidate selection against fixed `MultiPV` fixtures. No live engine required.
3. Measure wall-clock cost of one round at a couple of depth and `multipv` settings.
4. Wire the client effect and the animation.

## Decide this before building

Always penalizing the loser makes the deficit compound. Two losses at the clear band is about 600cp down. That is decided chess with no mate on the board. Later rounds then animate a game whose outcome was already settled.

Pick one of these now:

- Shrink the loser's allowed loss as their eval deficit grows.
- Clamp absolute eval to something like +/-800cp until mate unlocks in round 4.

Players no longer choose moves. Do not write copy that implies they did. The animation is the payoff of winning the round.
