import random


SUITS = ("S", "H", "D", "C")
SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def rank_label(rank):
    names = {1: "A", 11: "J", 12: "Q", 13: "K"}
    return names.get(rank, str(rank))


class Card:
    def __init__(self, suit, rank, face_up=False):
        self.suit = suit
        self.rank = rank
        self.face_up = face_up

    @property
    def color(self):
        return "red" if self.suit in ("H", "D") else "black"

    @property
    def key(self):
        return rank_label(self.rank) + self.suit

    @property
    def name(self):
        return rank_label(self.rank) + SUIT_SYMBOLS[self.suit]


class Deck:
    def __init__(self):
        self.cards = [Card(s, r) for s in SUITS for r in range(1, 14)]

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        return self.cards.pop()

    def __len__(self):
        return len(self.cards)
