import time


class FramePump:
    def __init__(self, dartsnut, renderer, game, logger=None):
        self.dartsnut = dartsnut
        self.renderer = renderer
        self.game = game
        self.logger = logger
        self.frame = None
        self.dirty = True
        self.accepted_writes = 0
        self.rejected_writes = 0
        self.render_count = 0
        self.last_render_ms = 0.0
        self.max_render_ms = 0.0
        self.longest_accepted_gap_ms = 0.0
        self.last_accepted_at = None
        self.last_stats_log_at = time.monotonic()

    def mark_dirty(self):
        self.dirty = True

    def update(self, now=None):
        now = time.monotonic() if now is None else now
        if self.dirty or self.frame is None:
            self.render_cached_frame()

        accepted = bool(self.dartsnut.update_frame_buffer(self.frame))
        if accepted:
            self.accepted_writes += 1
            if self.last_accepted_at is not None:
                gap_ms = (now - self.last_accepted_at) * 1000
                self.longest_accepted_gap_ms = max(self.longest_accepted_gap_ms, gap_ms)
            self.last_accepted_at = now
        else:
            self.rejected_writes += 1

        if now - self.last_stats_log_at >= 5:
            self.log_stats()
            self.last_stats_log_at = now
        return accepted

    def render_cached_frame(self):
        start = time.perf_counter()
        self.frame = bytearray(self.renderer.render(self.game).tobytes())
        self.last_render_ms = (time.perf_counter() - start) * 1000
        self.max_render_ms = max(self.max_render_ms, self.last_render_ms)
        self.render_count += 1
        self.dirty = False
        self.game.debug_message = self.stats_text()

    def stats_text(self):
        return f"a{self.accepted_writes} r{self.rejected_writes} {self.last_render_ms:.1f}ms"

    def log_stats(self):
        if not self.logger:
            return
        self.logger(
            "frame-pump "
            f"accepted={self.accepted_writes} rejected={self.rejected_writes} "
            f"renders={self.render_count} last_render_ms={self.last_render_ms:.2f} "
            f"max_render_ms={self.max_render_ms:.2f} "
            f"longest_accepted_gap_ms={self.longest_accepted_gap_ms:.2f}"
        )
