# Continuation planner

After each arcade round, play six half-moves (three full moves). The winner gets
Stockfish's best move on their turns. The loser gets a weaker move. How much
weaker comes from the point gap.

Do not aim at a target win percentage. Report the evaluation actually returned.

## Loss target from the score gap

```text
margin = (winner_score - loser_score) / maximum_possible_score
```

For PixelDarts Chess, `maximum_possible_score` is the sum of the three highest
cells on that round's grid, including the 25-point bull.

| Margin | Band | Loser target loss per ply |
|---:|---|---:|
| 0% | balanced | 0cp |
| 1–10% | small | 40cp |
| 11–25% | clear | 100cp |
| 26–40% | strong | 200cp |
| 41%+ | dominant | 350cp |

Loss is `best_score - candidate_score`, with both scores from the side to move.
Choose the candidate nearest the target. If every candidate loses less than the
target, choose the largest returned loss. Do not search for a worse move.

## Stockfish calls

Use one `engine.analyse` call per ply:

```text
engine.analyse(board, Limit(depth=10, time=0.12), multipv=N)
```

Push the selected move before the next fresh search. Stop on a terminal
position; never pad the continuation.

Rounds 1 through 3 request eight PVs on both sides so mating candidates can be
filtered. A winner chooses the best non-mating candidate. A loser applies the
loss target to non-mating candidates. If every returned legal move mates, play
the best mate.

From round 4, a winner requests PV1 and mate is allowed. A loser still requests
eight candidates, and mate scores participate in the closeness choice.
