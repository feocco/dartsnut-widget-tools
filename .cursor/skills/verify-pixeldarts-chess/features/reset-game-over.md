# Reset and game over

## Sub-features

B reset, stale analysis rejection, checkmate, and draw reasons.

## How to get to it (user POV)

Press B at any point to reset. Play until a terminal chess position to see game
over.

## Driving it with Dartsnut Agent

Start analysis, press B before it returns, and confirm the title remains after
the stale result arrives.

## Gotchas

The automated tests cover terminal positions more efficiently than manual play.
