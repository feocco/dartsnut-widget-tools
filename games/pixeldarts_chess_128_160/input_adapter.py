BUTTON_ALIASES = {
    "a": ("btn_a",),
    "b": ("btn_b",),
}


class DartsnutInputAdapter:
    def __init__(self, dartsnut, logger=None):
        self.dartsnut = dartsnut
        self.logger = logger
        self.last_active_darts = {}
        self.previous_buttons = {}
        self.last_button_snapshot = {}

    def button_events(self):
        method = getattr(self.dartsnut, "get_button_events", None)
        if method:
            events = normalize_buttons(method() or {})
            if events != self.last_button_snapshot:
                self.log(f"button-events normalized={events}")
                self.last_button_snapshot = dict(events)
            return [name for name in BUTTON_ALIASES if events.get(f"btn_{name}")]

        snapshot = self.button_snapshot()
        if snapshot:
            return self.edge_events(snapshot)
        return []

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
        events = []
        for event in self.poll_hit_events():
            x, y, color = normalize_hit(event)
            if x is not None and y is not None:
                events.append((int(x), int(y), color))
                self.log(f"dart hit x={int(x)} y={int(y)} color={color}")
                if isinstance(event, (tuple, list)) and len(event) >= 3:
                    self.last_active_darts[event[0]] = (int(x), int(y))

        for event in self.poll_moved_active_darts():
            x, y, color = normalize_hit(event)
            if x is not None and y is not None:
                events.append((int(x), int(y), color))
                self.log(f"dart active x={int(x)} y={int(y)} color={color}")
        return events

    def poll_hit_events(self):
        for method_name in ("get_dart_hits", "get_hits", "poll_hits", "read_hits"):
            method = getattr(self.dartsnut, method_name, None)
            if method:
                events = method() or []
                return events if isinstance(events, list) else [events]
        return []

    def poll_moved_active_darts(self):
        method = getattr(self.dartsnut, "get_active_darts", None)
        if not method:
            return []

        events = method() or []
        if not isinstance(events, list):
            events = [events]

        moved = []
        seen = set()
        for event in events:
            dart_index, x, y = normalize_active_dart(event)
            if dart_index is None or x is None or y is None:
                continue
            if x < 0 or y < 0:
                continue

            seen.add(dart_index)
            position = (int(x), int(y))
            if self.last_active_darts.get(dart_index) != position:
                self.last_active_darts[dart_index] = position
                moved.append((dart_index, position[0], position[1]))

        for dart_index in list(self.last_active_darts):
            if dart_index not in seen:
                del self.last_active_darts[dart_index]

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
