from dataclasses import dataclass


@dataclass(frozen=True)
class OpeningReply:
    key: str
    title: str
    subtitle: str
    line: tuple


@dataclass(frozen=True)
class OpeningFamily:
    key: str
    title: str
    subtitle: str
    replies: tuple


OPENING_FAMILIES = (
    OpeningFamily(
        key="london",
        title="London System",
        subtitle="London",
        replies=(
            OpeningReply("london_classical", "London System", "Classical", ("d2d4", "d7d5", "g1f3", "g8f6", "c1f4", "e7e6", "e2e3", "f8d6")),
            OpeningReply("indian_london", "Indian Game: London System", "Indian London", ("d2d4", "g8f6", "g1f3", "e7e6", "c1f4", "c7c5", "e2e3", "b7b6")),
            OpeningReply("dutch_london", "Dutch Defense vs London System", "Dutch", ("d2d4", "f7f5", "g1f3", "g8f6", "c1f4", "e7e6", "e2e3", "f8e7")),
        ),
    ),
    OpeningFamily(
        key="italian",
        title="Italian Game",
        subtitle="Italian",
        replies=(
            OpeningReply("italian", "Italian Game", "Italian", ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "c2c3", "g8f6")),
            OpeningReply("sicilian", "Sicilian Defense", "Sicilian", ("e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6")),
            OpeningReply("caro_kann", "Caro-Kann Defense", "Caro-Kann", ("e2e4", "c7c6", "d2d4", "d7d5", "e4d5", "c6d5", "g1f3", "g8f6")),
        ),
    ),
    OpeningFamily(
        key="queens_gambit",
        title="Queen's Gambit",
        subtitle="Q Gambit",
        replies=(
            OpeningReply("qgd", "Queen's Gambit Declined", "QGD", ("d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6", "c1g5", "f8e7")),
            OpeningReply("slav", "Slav Defense", "Slav", ("d2d4", "d7d5", "c2c4", "c7c6", "b1c3", "g8f6", "g1f3", "d5c4")),
            OpeningReply("accepted", "Queen's Gambit Accepted", "QGA", ("d2d4", "d7d5", "c2c4", "d5c4", "g1f3", "g8f6", "e2e3", "e7e6")),
        ),
    ),
)


def family_by_key(key):
    for family in OPENING_FAMILIES:
        if family.key == key:
            return family
    return None


def reply_by_key(family, key):
    for reply in family.replies:
        if reply.key == key:
            return reply
    return None
