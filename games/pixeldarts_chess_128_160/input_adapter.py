import time

BUTTON_ALIASES = {
    "a": ("btn_a",),
    "b": ("btn_b",),
}

# Match pydartsnut InputHandler.IDLE_UNBLOCK_DURATION so brief dropouts do not
# look like a new throw when falling back to get_active_darts.
ACTIVE_IDLE_CLEAR_SECONDS = 0.2


class DartsnutInputAdapter:
    def __init__(self, dartsnut, logger=None, clock=None):
        self.dartsnut = dartsnut
        self.logger = logger
        self.clock = clock or time.monotonic
        self.last_active_darts = {}
        self._active_absent_since = {}
        self.previous_buttons = {}
        self.last_button_snapshot = {}

    def button_events(self):
        events = []
        method = getattr(self.dartsnut, "get_button_events", None)
        if method:
            event_snapshot = normalize_buttons(method() or {})
            events.extend(name for name in BUTTON_ALIASES if event_snapshot.get(f"btn_{name}"))

        snapshot = self.button_snapshot()
        if snapshot:
            events.extend(self.edge_events(snapshot))
        return list(dict.fromkeys(events))

    def button_snapshot(self):
        for method_name in ("get_buttons", "get_button_state", "read_buttons"):
            method = getattr(self.dartsnut, method_name, None)
            if not method:
                continue
            raw = method() or {}
            snapshot = normalize_buttons(raw)
            if snapshot:
                if snapshot != self.last_button_snapshot:
                    self.log(f"buttons raw={raw} normalized={snapshot}")
                    self.last_button_snapshot = dict(snapshot)
                return snapshot
        return {}

    def edge_events(self, snapshot):
        events = []
        for name, aliases in BUTTON_ALIASES.items():
            pressed = any(snapshot.get(alias) for alias in aliases)
            was_pressed = any(self.previous_buttons.get(alias) for alias in aliases)
            if pressed and not was_pressed:
                events.append(name)
                self.log(f"button accepted={name}")
        self.previous_buttons = dict(snapshot)
        return events

    def hit_events(self):
        """Return edge-triggered dart impacts suitable for scoring.

        Prefer ``get_dart_hits`` (and aliases): pydartsnut already blocks a slot
        after one event until it goes idle. ``get_active_darts`` reports stuck
        positions every frame and must not score — including 1px jitter or a
        dart that remains lit across turn intros.
        """
        events = []
        if self._hit_method():
            for event in self.poll_hit_events():
                x, y, color = normalize_hit(event)
                if x is not None and y is not None:
                    events.append((int(x), int(y), color))
                    self.log(f"dart hit x={int(x)} y={int(y)} color={color}")
                    if isinstance(event, (tuple, list)) and len(event) >= 3:
                        dart_index = event[0]
                        self.last_active_darts[dart_index] = (int(x), int(y))
                        self._active_absent_since.pop(dart_index, None)
            # Track stuck darts without emitting scoring events.
            self._sync_active_darts(emit_appears=False)
            return events

        for event in self._sync_active_darts(emit_appears=True):
            x, y, color = normalize_hit(event)
            if x is not None and y is not None:
                events.append((int(x), int(y), color))
                self.log(f"dart active x={int(x)} y={int(y)} color={color}")
        return events

    def _hit_method(self):
        for method_name in ("get_dart_hits", "get_hits", "poll_hits", "read_hits"):
            method = getattr(self.dartsnut, method_name, None)
            if method:
                return method
        return None

    def poll_hit_events(self):
        method = self._hit_method()
        if not method:
            return []
        events = method() or []
        return events if isinstance(events, list) else [events]

    def _sync_active_darts(self, emit_appears):
        """Update stuck-dart tracking; optionally emit appear-only edges.

        Position changes while a dart stays present (hardware jitter) never
        emit. Absence only clears after ACTIVE_IDLE_CLEAR_SECONDS so brief
        dropouts do not look like a new throw.
        """
        method = getattr(self.dartsnut, "get_active_darts", None)
        if not method:
            return []

        events = method() or []
        if not isinstance(events, list):
            events = [events]

        moved = []
        seen = set()
        now = self.clock()
        for event in events:
            dart_index, x, y = normalize_active_dart(event)
            if dart_index is None or x is None or y is None:
                continue
            if x < 0 or y < 0:
                continue

            seen.add(dart_index)
            position = (int(x), int(y))
            self._active_absent_since.pop(dart_index, None)
            previous = self.last_active_darts.get(dart_index)
            if previous is None:
                self.last_active_darts[dart_index] = position
                if emit_appears:
                    moved.append((dart_index, position[0], position[1]))
            else:
                # Jitter / drift: remember the latest pixel but do not score.
                self.last_active_darts[dart_index] = position

        for dart_index in list(self.last_active_darts):
            if dart_index in seen:
                continue
            absent_since = self._active_absent_since.get(dart_index)
            if absent_since is None:
                self._active_absent_since[dart_index] = now
                continue
            if now - absent_since >= ACTIVE_IDLE_CLEAR_SECONDS:
                del self.last_active_darts[dart_index]
                del self._active_absent_since[dart_index]

        return moved

    def log(self, message):
        if self.logger:
            self.logger(message)


def normalize_buttons(raw):
    if isinstance(raw, dict):
        return {str(key): bool(value) for key, value in raw.items()}
    if isinstance(raw, int):
        return {
            "btn_a": bool(raw & 0x01),
            "btn_b": bool(raw & 0x02),
            "btn_up": bool(raw & 0x04),
            "btn_right": bool(raw & 0x08),
            "btn_left": bool(raw & 0x10),
            "btn_down": bool(raw & 0x20),
        }
    return {}


def normalize_hit(event):
    if isinstance(event, dict):
        return event.get("x"), event.get("y"), event.get("color")
    if isinstance(event, (tuple, list)) and len(event) >= 2:
        if len(event) >= 3 and isinstance(event[0], int) and 0 <= event[0] <= 11:
            return event[1], event[2], None
        color = event[2] if len(event) >= 3 else None
        return event[0], event[1], color
    return None, None, None


def normalize_active_dart(event):
    if isinstance(event, dict):
        dart_index = event.get("dart_index", event.get("index", 0))
        return dart_index, event.get("x"), event.get("y")
    if isinstance(event, (tuple, list)) and len(event) >= 3:
        return event[0], event[1], event[2]
    return None, None, None
