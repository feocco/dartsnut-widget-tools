import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import chess

FIXTURES = Path(__file__).with_name("fixtures")


@dataclass(frozen=True)
class OpeningPosition:
    key: str
    title: str
    eco: str
    aliases: tuple[str, ...]
    tags: tuple[str, ...]
    line: tuple[str, ...]
    expected_fen: str


@dataclass(frozen=True)
class OpeningReply:
    key: str
    title: str
    subtitle: str
    line: tuple[str, ...]


@dataclass(frozen=True)
class OpeningFamily:
    key: str
    title: str
    subtitle: str
    replies: tuple[OpeningReply, ...]


@dataclass(frozen=True)
class OpeningBook:
    schema_version: int
    initial_fen: str
    positions: tuple[OpeningPosition, ...]

    def position(self, key: str) -> OpeningPosition:
        for position in self.positions:
            if position.key == key:
                return position
        raise KeyError(f"Unknown opening position: {key}")


def _load_json(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return cast(dict[str, object], value)


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    return cast(list[str], value)


def load_opening_book(
    path: Path = FIXTURES / "opening_positions.v1.json",
) -> OpeningBook:
    data = _load_json(path)
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported opening fixture schema")
    initial_fen = data.get("initial_fen")
    rows = data.get("positions")
    if not isinstance(initial_fen, str) or not isinstance(rows, list):
        raise ValueError("Opening fixture needs initial_fen and positions")

    positions: list[OpeningPosition] = []
    keys: set[str] = set()
    for item in cast(list[object], rows):
        row = cast(dict[str, object], item) if isinstance(item, dict) else None
        if not isinstance(row, dict):
            raise ValueError("Opening positions must be objects")
        key = row.get("id")
        moves = row.get("moves_uci")
        expected_fen = row.get("expected_fen")
        title = row.get("name")
        eco = row.get("eco")
        if not isinstance(key, str) or key in keys:
            raise ValueError(f"Opening position id must be unique: {key!r}")
        moves = _string_list(moves, f"{key}.moves_uci")
        if not isinstance(expected_fen, str):
            raise ValueError(f"{key} needs expected_fen")
        if not isinstance(title, str) or not isinstance(eco, str):
            raise ValueError(f"{key} needs name and eco")
        board = chess.Board(initial_fen)
        for uci in moves:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError(f"{key} has illegal move {uci} in {board.fen()}")
            board.push(move)
        if board.fen() != expected_fen:
            raise ValueError(f"{key} expected_fen does not match its moves")
        if board.turn != chess.WHITE:
            raise ValueError(f"{key} must leave White to move")
        keys.add(key)
        positions.append(
            OpeningPosition(
                key=key,
                title=title,
                eco=eco,
                aliases=tuple(_string_list(row.get("aliases", []), f"{key}.aliases")),
                tags=tuple(_string_list(row.get("tags", []), f"{key}.tags")),
                line=tuple(moves),
                expected_fen=expected_fen,
            )
        )
    return OpeningBook(1, initial_fen, tuple(positions))


def load_opening_menu(
    book: OpeningBook,
    path: Path = FIXTURES / "opening_menu.v1.json",
) -> tuple[OpeningFamily, ...]:
    data = _load_json(path)
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported opening menu schema")
    rows = data.get("families")
    if not isinstance(rows, list):
        raise ValueError("Opening menu needs families")
    families: list[OpeningFamily] = []
    family_keys: set[str] = set()
    for item in cast(list[object], rows):
        row = cast(dict[str, object], item) if isinstance(item, dict) else None
        if row is None:
            raise ValueError("Opening families must be objects")
        key = row.get("id")
        title = row.get("title")
        subtitle = row.get("subtitle")
        if not isinstance(key, str) or key in family_keys:
            raise ValueError(f"Opening family id must be unique: {key!r}")
        if not isinstance(title, str) or not isinstance(subtitle, str):
            raise ValueError(f"{key} needs title and subtitle")
        position_keys = _string_list(row.get("positions"), f"{key}.positions")
        if len(position_keys) != 3 or len(set(position_keys)) != 3:
            raise ValueError(f"{key} must contain three unique positions")
        positions = [book.position(position_key) for position_key in position_keys]
        family_keys.add(key)
        families.append(
            OpeningFamily(
                key=key,
                title=title,
                subtitle=subtitle,
                replies=tuple(
                    OpeningReply(
                        key=position.key,
                        title=position.title,
                        subtitle=position.aliases[0] if position.aliases else position.title,
                        line=position.line,
                    )
                    for position in positions
                ),
            )
        )
    if len(families) != 3:
        raise ValueError("Opening menu must contain three families")
    return tuple(families)


OPENING_BOOK = load_opening_book()
OPENING_FAMILIES = load_opening_menu(OPENING_BOOK)


def family_by_key(key: str) -> OpeningFamily:
    for family in OPENING_FAMILIES:
        if family.key == key:
            return family
    raise KeyError(f"Unknown opening family: {key}")


def reply_by_key(family: OpeningFamily, key: str) -> OpeningReply:
    for reply in family.replies:
        if reply.key == key:
            return reply
    raise KeyError(f"Unknown opening position: {key}")
