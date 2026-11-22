import time

from cards import Deck
from structures import Stack, Queue, LinkedList


TABLEAU_IDS = [f"T{i}" for i in range(7)]
FOUNDATION_IDS = [f"F{i}" for i in range(4)]
DEST_IDS = TABLEAU_IDS + FOUNDATION_IDS


def is_valid_run(cards):
    if not all(card.face_up for card in cards):
        return False
    for upper, lower in zip(cards, cards[1:]):
        if upper.color == lower.color or upper.rank != lower.rank + 1:
            return False
    return True


class Game:
    def __init__(self, draw_count=1, time_limit=600):
        self.draw_count = draw_count
        self.time_limit = time_limit
        self.new_game()


    def new_game(self):
        deck = Deck()
        deck.shuffle()

        self.tableau = [LinkedList() for _ in range(7)]
        self.foundations = [Stack() for _ in range(4)]
        self.stock = Queue()
        self.waste = Stack()


        self.piles = {"stock": self.stock, "waste": self.waste}
        for i in range(4):
            self.piles[f"F{i}"] = self.foundations[i]
        for i in range(7):
            self.piles[f"T{i}"] = self.tableau[i]


        for i in range(7):
            for j in range(i + 1):
                card = deck.deal()
                card.face_up = (j == i)
                self.tableau[i].push(card)


        while len(deck) > 0:
            self.stock.enqueue(deck.deal())

        self.undo_stack = Stack()
        self.redo_stack = Stack()
        self.score = 0
        self.bonus = 0
        self.start_time = None
        self.end_time = None
        self.won = False
        self.lost = False
        self.paused = False
        self.pause_started = None
        self.paused_for = 0
        self.positions = {}
        self.refresh_positions()

    def refresh_positions(self):
        self.positions = {}
        for pile_id, pile in self.piles.items():
            for index, card in enumerate(pile.to_list()):
                self.positions[card.key] = {
                    "pile": pile_id, "index": index, "face_up": card.face_up,
                }

    def find_card(self, key):
        return self.positions.get(key)

    def snapshot(self):
        layout = tuple(
            (pile_id, tuple((c.key, c.face_up) for c in pile.to_list()))
            for pile_id, pile in self.piles.items()
        )
        return (layout, self.score)


    @staticmethod
    def fits_tableau(card, pile):
        if pile.is_empty():
            return card.rank == 13
        top = pile.peek()
        return top.face_up and top.color != card.color and top.rank == card.rank + 1

    @staticmethod
    def fits_foundation(card, pile):
        if pile.is_empty():
            return card.rank == 1
        top = pile.peek()
        return top.suit == card.suit and card.rank == top.rank + 1

    def can_move(self, src, dst, count=1):

        if src == dst or src == "stock" or dst in ("stock", "waste"):
            return False
        if src.startswith("F") and dst.startswith("F"):
            return False

        pile = self.piles[src]
        if count < 1 or count > len(pile):
            return False
        if count > 1 and not src.startswith("T"):
            return False

        cards = pile.to_list()[-count:]
        if not is_valid_run(cards):
            return False

        if dst.startswith("F"):
            return count == 1 and self.fits_foundation(cards[0], self.piles[dst])
        return self.fits_tableau(cards[0], self.piles[dst])

    @staticmethod
    def score_for(src, dst):
        if src == "waste":
            return 10 if dst.startswith("F") else 5
        if src.startswith("T"):
            return 10 if dst.startswith("F") else 0
        return -15


    def move(self, src, dst, count=1):
        if self.is_locked() or not self.can_move(src, dst, count):
            return False


        pile = self.piles[src]
        flip = False
        if src.startswith("T") and len(pile) > count:
            flip = not pile.get(len(pile) - count - 1).face_up

        points = self.score_for(src, dst) + (5 if flip else 0)
        record = {
            "kind": "move", "src": src, "dst": dst, "count": count, "flip": flip,
            "before": self.score, "after": max(0, self.score + points),
        }
        self._commit(record)
        return True

    def draw(self):
        if self.is_locked():
            return False
        if not self.stock.is_empty():
            cards = self.stock.peek_n(self.draw_count)
            record = {"kind": "draw", "cards": cards,
                      "before": self.score, "after": self.score}
        elif not self.waste.is_empty():
            record = {"kind": "recycle", "cards": self.waste.to_list(),
                      "before": self.score, "after": max(0, self.score - 50)}
        else:
            return False
        self._commit(record)
        return True

    def _commit(self, record):
        self._apply(record)
        self.undo_stack.push(record)
        self.redo_stack.clear()
        if self.start_time is None:
            self.start_time = time.time()
        self.refresh_positions()
        self.check_win()

    def _apply(self, record):
        kind = record["kind"]
        if kind == "move":
            cards = self.piles[record["src"]].take_top(record["count"])
            for card in cards:
                self.piles[record["dst"]].push(card)
            if record["flip"]:
                self.piles[record["src"]].peek().face_up = True
        elif kind == "draw":
            for _ in record["cards"]:
                card = self.stock.dequeue()
                card.face_up = True
                self.waste.push(card)
        else:
            self.waste.clear()
            for card in record["cards"]:
                card.face_up = False
                self.stock.enqueue(card)
        self.score = record["after"]

    def _revert(self, record):
        kind = record["kind"]
        if kind == "move":
            if record["flip"]:
                self.piles[record["src"]].peek().face_up = False
            cards = self.piles[record["dst"]].take_top(record["count"])
            for card in cards:
                self.piles[record["src"]].push(card)
        elif kind == "draw":
            for _ in record["cards"]:
                self.waste.pop()
            for card in reversed(record["cards"]):
                card.face_up = False
                self.stock.push_front(card)
        else:
            self.stock.clear()
            for card in record["cards"]:
                card.face_up = True
                self.waste.push(card)
        self.score = record["before"]

    def undo(self):
        if self.is_locked() or self.undo_stack.is_empty():
            return False
        record = self.undo_stack.pop()
        self._revert(record)
        self.redo_stack.push(record)
        self.refresh_positions()
        return True

    def redo(self):
        if self.is_locked() or self.redo_stack.is_empty():
            return False
        record = self.redo_stack.pop()
        self._apply(record)
        self.undo_stack.push(record)
        self.refresh_positions()
        self.check_win()
        return True


    def check_win(self):
        if not self.won and sum(len(f) for f in self.foundations) == 52:
            self.won = True
            self.end_time = time.time()
            seconds = max(30, self.elapsed())
            self.bonus = 700000 // seconds
            self.score += self.bonus
        return self.won

    def is_won(self):
        return self.won

    def elapsed(self):
        if self.start_time is None:
            return 0
        if self.end_time:
            end = self.end_time
        elif self.paused:
            end = self.pause_started
        else:
            end = time.time()
        return int(end - self.start_time - self.paused_for)

    def time_left(self):
        if self.start_time is None:
            return self.time_limit
        return max(0, self.time_limit - self.elapsed())

    def check_time(self):
        if (not self.won and not self.lost and not self.paused
                and self.start_time is not None and self.elapsed() >= self.time_limit):
            self.lost = True
            self.end_time = self.start_time + self.paused_for + self.time_limit
        return self.lost

    def is_locked(self):
        self.check_time()
        return self.won or self.lost or self.paused

    def pause(self):
        if self.start_time is None or self.won or self.lost or self.paused:
            return False
        self.paused = True
        self.pause_started = time.time()
        return True

    def resume(self):
        if not self.paused:
            return False
        self.paused_for += time.time() - self.pause_started
        self.paused = False
        self.pause_started = None
        return True

    def toggle_pause(self):
        return self.resume() if self.paused else self.pause()


    def can_auto_finish(self):
        if self.is_locked() or not self.stock.is_empty() or not self.waste.is_empty():
            return False
        return all(card.face_up for pile in self.tableau for card in pile.to_list())

    def auto_finish_step(self):
        for src in ["waste"] + TABLEAU_IDS:
            if self.piles[src].is_empty():
                continue
            for dst in FOUNDATION_IDS:
                if self.can_move(src, dst, 1):
                    return self.move(src, dst, 1)
        return False


    def describe_target(self, dst):
        pile = self.piles[dst]
        return "an empty column" if pile.is_empty() else pile.peek().name

    def find_hint(self):
        options = []


        for src in ["waste"] + TABLEAU_IDS:
            top = self.piles[src].peek()
            if top is None:
                continue
            for dst in FOUNDATION_IDS:
                if self.can_move(src, dst, 1):
                    options.append((0, {"kind": "move", "src": src, "dst": dst, "count": 1,
                                        "text": f"Move {top.name} to the foundation"}))
                    break


        for src in TABLEAU_IDS:
            cards = self.piles[src].to_list()
            for start, card in enumerate(cards):
                if not card.face_up:
                    continue
                count = len(cards) - start
                reveals = start > 0 and not cards[start - 1].face_up
                moves_whole_column = start == 0 and card.rank != 13
                if not (reveals or moves_whole_column):
                    continue
                priority = 1 if reveals else 3
                for dst in TABLEAU_IDS:
                    if dst != src and self.can_move(src, dst, count):
                        text = f"Move {card.name} onto {self.describe_target(dst)}"
                        options.append((priority, {"kind": "move", "src": src, "dst": dst,
                                                   "count": count, "text": text}))


        if not self.waste.is_empty():
            top = self.waste.peek()
            for dst in TABLEAU_IDS:
                if self.can_move("waste", dst, 1):
                    text = f"Move {top.name} onto {self.describe_target(dst)}"
                    options.append((2, {"kind": "move", "src": "waste", "dst": dst,
                                        "count": 1, "text": text}))


        if not self.stock.is_empty():
            options.append((5, {"kind": "draw", "src": "stock", "dst": "waste",
                                "count": 0, "text": "Draw from the stock"}))
        elif not self.waste.is_empty():
            options.append((6, {"kind": "draw", "src": "stock", "dst": "waste",
                                "count": 0, "text": "Recycle the waste pile into the stock"}))

        if not options:
            return None
        return min(options, key=lambda option: option[0])[1]
