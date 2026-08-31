"""Regression: sticky / jittering hardware darts must not multi-score.

pydartsnut exposes both edge-triggered ``get_dart_hits`` (blocked until idle)
and continuous ``get_active_darts`` (stuck positions every frame). Scoring must
use the edge API so one physical dart cannot consume a whole turn, and a dart
that remains lit across ``turn_intro`` must not score for the next player.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

from input_adapter import ACTIVE_IDLE_CLEAR_SECONDS, DartsnutInputAdapter  # noqa: E402
from match import Match, MatchPhase  # noqa: E402


class StickyBoard:
    """Minimal pydartsnut-shaped surface: get_dart_hits + get_active_darts."""

    IDLE_UNBLOCK = 0.2

    def __init__(self, clock=None):
        self.darts = [[-1, -1] for _ in range(12)]
        self._blocked: set[int] = set()
        self._last = None
        self._idle_start: dict[int, float] = {}
        self.clock = clock or time.time

    def set_slot(self, index: int, x: int, y: int) -> None:
        self.darts[index] = [x, y]

    def clear_slot(self, index: int) -> None:
        self.darts[index] = [-1, -1]

    def get_darts(self):
        return [list(p) for p in self.darts]

    def get_dart_hits(self):
        raw = self.get_darts()
        hits = []
        if self._last is None:
            self._last = raw
            return hits
        now = self.clock()
        for index, dart in enumerate(raw):
            invalid = dart[0] < 0 or dart[1] < 0 or (dart[0] == 0 and dart[1] == 0)
            if index in self._blocked:
                if invalid:
                    self._idle_start.setdefault(index, now)
                    if now - self._idle_start[index] >= self.IDLE_UNBLOCK:
                        self._blocked.discard(index)
                        self._idle_start.pop(index, None)
                else:
                    self._idle_start.pop(index, None)
            elif not invalid:
                hits.append((index, dart[0], dart[1]))
                self._blocked.add(index)
        self._last = raw
        return hits

    def get_active_darts(self):
        active = []
        for index, dart in enumerate(self.get_darts()):
            if dart[0] >= 0 and dart[1] >= 0 and not (dart[0] == 0 and dart[1] == 0):
                active.append((index, dart[0], dart[1]))
        return active

    def get_buttons(self):
        return {"btn_a": False, "btn_b": False}


class ActiveOnlyBoard:
    """Board that only exposes get_active_darts (adapter fallback path)."""

    def __init__(self):
        self.darts = [[-1, -1] for _ in range(12)]

    def set_slot(self, index: int, x: int, y: int) -> None:
        self.darts[index] = [x, y]

    def clear_slot(self, index: int) -> None:
        self.darts[index] = [-1, -1]

    def get_active_darts(self):
        active = []
        for index, dart in enumerate(self.darts):
            if dart[0] >= 0 and dart[1] >= 0 and not (dart[0] == 0 and dart[1] == 0):
                active.append((index, dart[0], dart[1]))
        return active

    def get_buttons(self):
        return {"btn_a": False, "btn_b": False}


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def make_match():
    game = Match(evaluator=object(), seed_source=lambda n: 1000 + n)
    game.planner = type(
        "P",
        (),
        {"plan": lambda self, r: (_ for _ in ()).throw(RuntimeError("no plan"))},
    )()
    return game


def enter_targets(game, now=0.0):
    game.handle_button("a", now)
    game.handle_button("a", now)
    assert game.phase == MatchPhase.TARGETS


def pump(adapter, game, frames, now_start=0.0, dt=0.05, clock=None):
    accepted = 0
    emitted = 0
    now = now_start
    for _ in range(frames):
        if clock is not None:
            clock.now = now
        game.tick(now)
        for x, y, color in adapter.hit_events():
            emitted += 1
            if game.handle_hit(x, y, color=color, now=now):
                accepted += 1
        now += dt
    return emitted, accepted, now


class StickyDartHitTests(unittest.TestCase):
    def test_stable_sticky_dart_scores_once(self):
        board = StickyBoard()
        adapter = DartsnutInputAdapter(board)
        game = make_match()
        enter_targets(game)
        board.set_slot(0, 64, 64)
        emitted, accepted, _ = pump(adapter, game, frames=40)
        self.assertEqual(emitted, 1)
        self.assertEqual(accepted, 1)
        self.assertEqual(game.target_round.darts_thrown["white"], 1)
        self.assertEqual(game.phase, MatchPhase.TARGETS)

    def test_one_pixel_jitter_does_not_rescore(self):
        board = StickyBoard()
        adapter = DartsnutInputAdapter(board)
        game = make_match()
        enter_targets(game)
        emitted = 0
        accepted = 0
        now = 0.0
        for frame in range(40):
            board.set_slot(0, 64 + (frame % 2), 64)
            game.tick(now)
            for x, y, color in adapter.hit_events():
                emitted += 1
                if game.handle_hit(x, y, color=color, now=now):
                    accepted += 1
            now += 0.05
        self.assertEqual(emitted, 1)
        self.assertEqual(accepted, 1)
        self.assertEqual(game.target_round.darts_thrown["white"], 1)
        self.assertEqual(game.target_round.darts_thrown["black"], 0)
        self.assertEqual(game.phase, MatchPhase.TARGETS)

    def test_brief_dropout_does_not_rescore(self):
        clock = FakeClock()
        board = StickyBoard(clock=clock)
        adapter = DartsnutInputAdapter(board, clock=clock)
        game = make_match()
        enter_targets(game)
        emitted = 0
        accepted = 0
        now = 0.0
        for frame in range(40):
            clock.now = now
            if 12 <= frame <= 14:
                board.clear_slot(0)
            else:
                board.set_slot(0, 64, 64)
            game.tick(now)
            for x, y, color in adapter.hit_events():
                emitted += 1
                if game.handle_hit(x, y, color=color, now=now):
                    accepted += 1
            now += 0.05
        # Dropout spans 0.15s < IDLE_UNBLOCK, so hardware stays blocked.
        self.assertEqual(emitted, 1)
        self.assertEqual(accepted, 1)
        self.assertEqual(game.target_round.darts_thrown["white"], 1)

    def test_sticky_dart_across_turn_intro_does_not_score_for_next_player(self):
        clock = FakeClock()
        board = StickyBoard(clock=clock)
        adapter = DartsnutInputAdapter(board, clock=clock)
        game = make_match()
        enter_targets(game)
        now = 0.0
        for slot, cell in enumerate(game.target_round.cells[:3]):
            board.set_slot(slot, *cell.center)
            for _ in range(5):
                clock.now = now
                game.tick(now)
                for x, y, color in adapter.hit_events():
                    game.handle_hit(x, y, color=color, now=now)
                now += 0.05
            board.clear_slot(slot)
            for _ in range(8):
                clock.now = now
                game.tick(now)
                list(adapter.hit_events())
                now += 0.05

        self.assertEqual(game.phase, MatchPhase.TURN_INTRO)
        self.assertEqual(game.target_round.darts_thrown["white"], 3)
        self.assertEqual(game.target_round.darts_thrown["black"], 0)

        board.set_slot(0, 64, 64)
        accepted_black = 0
        for _ in range(50):
            clock.now = now
            game.tick(now)
            for x, y, color in adapter.hit_events():
                shot = game.handle_hit(x, y, color=color, now=now)
                if shot is not None and game.target_round.darts_thrown.get("black", 0):
                    accepted_black += 1
            now += 0.1

        self.assertEqual(game.target_round.darts_thrown["black"], 0)
        self.assertEqual(accepted_black, 0)
        # Intro may auto-advance via tick; sticky dart still must not score.
        self.assertIn(game.phase, (MatchPhase.TURN_INTRO, MatchPhase.TARGETS))

    def test_active_only_fallback_ignores_jitter_and_brief_dropout(self):
        clock = FakeClock()
        board = ActiveOnlyBoard()
        adapter = DartsnutInputAdapter(board, clock=clock)
        game = make_match()
        enter_targets(game)

        board.set_slot(0, 64, 64)
        emitted, accepted, now = pump(adapter, game, frames=5, clock=clock)
        self.assertEqual(emitted, 1)
        self.assertEqual(accepted, 1)

        for frame in range(20):
            clock.now = now
            board.set_slot(0, 64 + (frame % 2), 64)
            for x, y, color in adapter.hit_events():
                emitted += 1
                if game.handle_hit(x, y, color=color, now=now):
                    accepted += 1
            now += 0.05
        self.assertEqual(emitted, 1)
        self.assertEqual(accepted, 1)

        # Brief dropout under idle clear window must not re-emit.
        for _ in range(2):
            clock.now = now
            board.clear_slot(0)
            list(adapter.hit_events())
            now += 0.05
        self.assertLess(2 * 0.05, ACTIVE_IDLE_CLEAR_SECONDS)
        board.set_slot(0, 64, 64)
        clock.now = now
        events = list(adapter.hit_events())
        self.assertEqual(events, [])

        # After a full idle clear, a reappearance is a new throw.
        for _ in range(5):
            clock.now = now
            board.clear_slot(0)
            list(adapter.hit_events())
            now += 0.05
        self.assertGreaterEqual(5 * 0.05, ACTIVE_IDLE_CLEAR_SECONDS)
        board.set_slot(0, 70, 70)
        clock.now = now
        events = list(adapter.hit_events())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][:2], (70, 70))


if __name__ == "__main__":
    unittest.main()
