# Continuation planner

After each arcade round, play six half-moves (three full moves). The winner gets Stockfish's best move on their turns. The loser gets a weaker move. How much weaker comes from the point gap.

Do not aim at a target win percentage. Report the eval you actually get.

## Loss target from the score gap

The band is the point difference, scaled by the best score a player can post this round.

```text
margin = (winner_score - loser_score) / maximum_possible_score
```

`maximum_possible_score` is the sum of the three highest cells on that round's grid, ignoring the bomb. Example: 75 + 50 + 50 = 175.

Example round: White 130, Black 90, max 175.

```text
margin = (130 - 90) / 175 = 0.23  →  23%  →  clear  →  100cp
```

That 100cp is the loss target for **each** of the loser's three plies, not a total for the line.

| Margin | Band | Loser target loss per ply |
|---:|---|---:|
| 0% | balanced | 0cp (both sides play best) |
| 1-10% | small | 40cp |
| 11-25% | clear | 100cp |
| 26-40% | strong | 200cp |
| 41%+ | dominant | 350cp |

These cp numbers are starting buckets, not derived from the dart scores. A 23% win and a 12% win both map to "clear" and both use 100cp.

On a loser ply, Stockfish returns several scored candidates. Loss of a candidate is `best_score - candidate_score`, both from the side to move. Play the candidate whose loss is closest to the band's target. 87cp beats 140cp when the target is 100cp. If every candidate loses less than the target, take the largest available loss. Do not search further for a worse move.

Winner plies ignore the band. They always play the best move.

## How to call Stockfish

Do not loop every legal move. One `engine.analyse` per ply.

```text
engine.analyse(board, Limit(depth=10, time=0.12), multipv=N)
```

`multipv=N` returns the top N moves with scores from one shared search.

Winner ply. `N=1`. Play PV1.

Loser ply. `N=8`. Drop mate scores when mate is locked (below). Pick the remaining candidate closest to the target loss. Push that move. Repeat from the new position.

Six calls total. Scores are always from the side about to move.

## Algorithm

1. Compute margin and look up the per-ply loss target.
2. For ply 1..6, on the current board:
   - If it is the winner's turn, analyse with `multipv=1` and play the best move.
   - If it is the loser's turn, analyse with `multipv=8` and play the candidate closest to the loss target.
3. After each push, the next call is a fresh search. The winner's next best move already uses whatever the loser just gave up. No tree of continuations.

A 100cp target on three loser plies lands near a 300cp swing because each search is from the position that already ate the previous loss. That is expected, not a second multiplier you apply by hand.

If the position ends early (stalemate, insufficient material, or mate when allowed), stop. Do not pad the line.

## Checkmate

Rounds 1-3. Skip any candidate whose score is a mate, including a winner best-move that mates. If that leaves no moves, play the best non-mating legal move. If every legal move mates, play it.

Rounds 4+. Mate is allowed. On dominant, a mate score can win the closeness pick.

If filtering empties the list, same fallback as rounds 1-3.
