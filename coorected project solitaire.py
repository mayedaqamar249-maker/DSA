import random
import sys
import time
from collections import deque
import tkinter as tk
from tkinter import messagebox


SUITS = ("S", "H", "D", "C")
SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}

TABLEAU_IDS = [f"T{i}" for i in range(7)]
FOUNDATION_IDS = [f"F{i}" for i in range(4)]
DEST_IDS = TABLEAU_IDS + FOUNDATION_IDS


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


class Stack:

    def __init__(self):
        self.items = []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return self.items.pop() if self.items else None

    def peek(self):
        return self.items[-1] if self.items else None

    def take_top(self, count):
        taken = self.items[-count:]
        del self.items[-count:]
        return taken

    def is_empty(self):
        return not self.items

    def to_list(self):
        return list(self.items)

    def clear(self):
        self.items = []

    def __len__(self):
        return len(self.items)


class Queue:

    def __init__(self):
        self.items = deque()

    def enqueue(self, item):
        self.items.append(item)

    def dequeue(self):
        return self.items.popleft() if self.items else None

    def push_front(self, item):
        self.items.appendleft(item)

    def peek(self):
        return self.items[0] if self.items else None

    def peek_n(self, count):
        return list(self.items)[:count]

    def is_empty(self):
        return not self.items

    def to_list(self):
        return list(self.items)

    def clear(self):
        self.items.clear()

    def __len__(self):
        return len(self.items)


class Node:

    def __init__(self, card):
        self.card = card
        self.prev = None
        self.next = None


class LinkedList:

    def __init__(self):
        self.head = None
        self.tail = None
        self.length = 0

    def push(self, card):
        node = Node(card)
        if self.tail is None:
            self.head = node
        else:
            node.prev = self.tail
            self.tail.next = node
        self.tail = node
        self.length += 1

    def pop(self):
        if self.tail is None:
            return None
        node = self.tail
        self.tail = node.prev
        if self.tail is None:
            self.head = None
        else:
            self.tail.next = None
        self.length -= 1
        return node.card

    def peek(self):
        return self.tail.card if self.tail else None

    def get(self, index):
        if index < 0 or index >= self.length:
            raise IndexError("index out of range")
        node = self.head
        for _ in range(index):
            node = node.next
        return node.card

    def take_top(self, count):
        cards = [self.pop() for _ in range(count)]
        cards.reverse()
        return cards

    def is_empty(self):
        return self.length == 0

    def to_list(self):
        cards = []
        node = self.head
        while node:
            cards.append(node.card)
            node = node.next
        return cards

    def clear(self):
        self.head = None
        self.tail = None
        self.length = 0

    def __len__(self):
        return self.length


def is_valid_run(cards):
    if not all(card.face_up for card in cards):
        return False
    for upper, lower in zip(cards, cards[1:]):
        if upper.color == lower.color or upper.rank != lower.rank + 1:
            return False
    return True


class Game:
    def __init__(self, draw_count=1):
        self.draw_count = draw_count
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
        if self.won or not self.can_move(src, dst, count):
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
        if self.won:
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
        if self.won or self.undo_stack.is_empty():
            return False
        record = self.undo_stack.pop()
        self._revert(record)
        self.redo_stack.push(record)
        self.refresh_positions()
        return True

    def redo(self):
        if self.won or self.redo_stack.is_empty():
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
        end = self.end_time if self.end_time else time.time()
        return int(end - self.start_time)


    def can_auto_finish(self):
        if self.won or not self.stock.is_empty() or not self.waste.is_empty():
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


class SolitaireApp:

    CARD_W = 100
    CARD_H = 140
    GAP = 20
    MARGIN = 40
    TOP_Y = 24
    TABLEAU_Y = 204
    CANVAS_W = 900
    CANVAS_H = 730


    BG = "#1e0b36"
    DEEP = "#2b0f4d"
    FELT = "#3a1466"
    FELT_EDGE = "#7b2cbf"
    SLOT = "#33125c"
    PINK = "#ff5fa2"
    PINK_HOVER = "#ff7fb6"
    LIGHT_PINK = "#ffc2e0"
    DISABLED = "#4a2272"
    CARD_FACE = "#fff4fa"
    CARD_EDGE = "#c98bb9"
    RED_SUIT = "#e11d74"
    BLACK_SUIT = "#4a148c"

    def __init__(self, root):
        self.root = root
        self.root.title("Klondike Solitaire")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        self.draw_count = 1
        self.game = Game(self.draw_count)

        self.card_rects = {}
        self.hitboxes = []
        self.press = None
        self.last_click = None
        self.hint = None
        self.hint_job = None
        self.confetti_job = None
        self.particles = []
        self.confetti_frame = 0
        self.busy = False

        self.build_ui()

        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-n>", lambda e: self.new_game(True))
        self.root.bind("<h>", lambda e: self.show_hint())
        self.root.bind("<H>", lambda e: self.show_hint())

        self.redraw()
        self.update_stats()
        self.set_status("Drag cards to move them. Click the stock to draw. "
                        "Double click a card to send it to the foundation.")
        self.tick()

    def col_x(self, i):
        return self.MARGIN + i * (self.CARD_W + self.GAP)


    def build_ui(self):

        header = tk.Frame(self.root, bg=self.DEEP)
        header.pack(fill="x")
        tk.Label(header, text="♥  Klondike Solitaire  ♠", bg=self.DEEP,
                 fg=self.PINK, font=("Georgia", 20, "bold")).pack(side="left", padx=20, pady=10)

        self.score_var = tk.StringVar()
        self.moves_var = tk.StringVar()
        self.time_var = tk.StringVar()
        for var in (self.time_var, self.moves_var, self.score_var):
            tk.Label(header, textvariable=var, bg=self.FELT, fg=self.LIGHT_PINK,
                     font=("Segoe UI", 11, "bold"), padx=12, pady=5).pack(side="right", padx=6, pady=10)


        bar = tk.Frame(self.root, bg=self.BG)
        bar.pack(fill="x", padx=14, pady=(8, 4))
        self.btn_new = self.make_button(bar, "New Game", lambda: self.new_game(True))
        self.btn_undo = self.make_button(bar, "Undo", self.undo)
        self.btn_redo = self.make_button(bar, "Redo", self.redo)
        self.btn_hint = self.make_button(bar, "Hint", self.show_hint)
        self.btn_auto = self.make_button(bar, "Auto Finish", self.auto_finish)
        self.btn_draw = self.make_button(bar, "Draw: 1", self.toggle_draw)


        self.canvas = tk.Canvas(self.root, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)


        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var, bg=self.DEEP, fg=self.LIGHT_PINK,
                 font=("Segoe UI", 10), anchor="w", padx=14, pady=6).pack(fill="x")

    def make_button(self, parent, text, command):
        button = tk.Button(parent, text=text, command=command, bg=self.PINK, fg="white",
                           activebackground=self.PINK_HOVER, activeforeground="white",
                           disabledforeground="#b48ac9", relief="flat", bd=0,
                           padx=14, pady=7, font=("Segoe UI", 10, "bold"), cursor="hand2")
        button.pack(side="left", padx=4)


        def hover(color):
            if str(button["state"]) == "normal":
                button.config(bg=color)
        button.bind("<Enter>", lambda e: hover(self.PINK_HOVER))
        button.bind("<Leave>", lambda e: hover(self.PINK))
        return button

    def set_enabled(self, button, enabled):
        button.config(state="normal" if enabled else "disabled",
                      bg=self.PINK if enabled else self.DISABLED)

    def set_status(self, text):
        self.status_var.set(text)

    def update_stats(self):
        g = self.game
        seconds = g.elapsed()
        self.time_var.set(f"Time  {seconds // 60:02d}:{seconds % 60:02d}")
        self.moves_var.set(f"Moves  {len(g.undo_stack)}")
        self.score_var.set(f"Score  {g.score}")

        idle = not g.won and not self.busy
        self.set_enabled(self.btn_undo, idle and not g.undo_stack.is_empty())
        self.set_enabled(self.btn_redo, idle and not g.redo_stack.is_empty())
        self.set_enabled(self.btn_hint, idle)
        self.set_enabled(self.btn_auto, not self.busy and g.can_auto_finish())

    def tick(self):
        seconds = self.game.elapsed()
        self.time_var.set(f"Time  {seconds // 60:02d}:{seconds % 60:02d}")
        self.root.after(500, self.tick)


    def round_rect(self, x1, y1, x2, y2, r, **options):
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(points, smooth=True, **options)

    def draw_slot(self, x, y, label=""):
        self.round_rect(x, y, x + self.CARD_W, y + self.CARD_H, 10, fill=self.SLOT,
                        outline=self.LIGHT_PINK, width=2, dash=(5, 4))
        if label:
            self.canvas.create_text(x + self.CARD_W / 2, y + self.CARD_H / 2, text=label,
                                    fill="#8d5bb5", font=("Georgia", 34, "bold"))

    def draw_card(self, x, y, card, tags=()):
        w, h = self.CARD_W, self.CARD_H

        self.round_rect(x + 3, y + 4, x + w + 3, y + h + 4, 10,
                        fill="#170626", outline="", tags=tags)
        if card.face_up:
            self.draw_card_front(x, y, card, tags)
        else:
            self.draw_card_back(x, y, tags)

    def draw_card_front(self, x, y, card, tags):
        w, h = self.CARD_W, self.CARD_H
        color = self.RED_SUIT if card.color == "red" else self.BLACK_SUIT

        self.round_rect(x, y, x + w, y + h, 10, fill=self.CARD_FACE,
                        outline=self.CARD_EDGE, width=2, tags=tags)
        if card.rank >= 11:
            self.round_rect(x + 18, y + 36, x + w - 18, y + h - 36, 8,
                            fill="#ffe3f1", outline=color, width=2, tags=tags)

        font = ("Georgia", 15, "bold")
        self.canvas.create_text(x + 9, y + 6, text=card.name, anchor="nw",
                                fill=color, font=font, tags=tags)
        self.canvas.create_text(x + w - 9, y + h - 6, text=card.name, anchor="se",
                                fill=color, font=font, tags=tags)
        self.canvas.create_text(x + w / 2, y + h / 2 + 4, text=SUIT_SYMBOLS[card.suit],
                                fill=color, font=("Arial", 40), tags=tags)

    def draw_card_back(self, x, y, tags):
        w, h = self.CARD_W, self.CARD_H
        self.round_rect(x, y, x + w, y + h, 10, fill="#5b1b8f",
                        outline="#ffb3d9", width=2, tags=tags)
        self.round_rect(x + 8, y + 8, x + w - 8, y + h - 8, 6, fill="#7e2bb8",
                        outline="#ff7ab8", width=1, tags=tags)

        for row in range(4):
            for col in range(3):
                cx = x + 22 + col * 28
                cy = y + 28 + row * 28
                self.canvas.create_polygon(cx, cy - 11, cx + 9, cy, cx, cy + 11, cx - 9, cy,
                                           fill="#a23fd6", outline="#ff9ccc", tags=tags)


    def redraw(self, hidden=None):
        hidden = hidden or set()
        self.canvas.delete("all")
        self.hitboxes = []
        self.card_rects = {}


        self.round_rect(12, 8, self.CANVAS_W - 12, self.CANVAS_H - 8, 22, fill=self.FELT,
                        outline=self.FELT_EDGE, width=3)
        self.canvas.create_text(self.CANVAS_W / 2, self.CANVAS_H - 52,
                                text="♥  ♠  ♦  ♣",
                                fill="#4a1d7d", font=("Arial", 44))

        self.draw_stock()
        self.draw_waste(hidden)
        self.draw_foundations(hidden)
        self.draw_tableau(hidden)
        if self.hint:
            self.draw_hint()

    def draw_stock(self):
        g = self.game
        x = self.col_x(0)
        if g.stock.is_empty():

            self.draw_slot(x, self.TOP_Y, "↻" if not g.waste.is_empty() else "")
        else:
            self.draw_card(x, self.TOP_Y, g.stock.peek())
            self.canvas.create_text(x + self.CARD_W / 2, self.TOP_Y + self.CARD_H + 14,
                                    text=f"{len(g.stock)} cards", fill=self.LIGHT_PINK,
                                    font=("Segoe UI", 10, "bold"))
        self.hitboxes.append((x, self.TOP_Y, x + self.CARD_W, self.TOP_Y + self.CARD_H, "stock", 0))

    def draw_waste(self, hidden):
        g = self.game
        x = self.col_x(1)
        self.draw_slot(x, self.TOP_Y)

        cards = g.waste.to_list()
        total = len(cards)
        shown = min(total, 3)
        for k in range(shown):
            index = total - shown + k

            px = x + k * 24 if g.draw_count == 3 else x
            self.card_rects[("waste", index)] = (px, self.TOP_Y)
            if ("waste", index) not in hidden:
                self.draw_card(px, self.TOP_Y, cards[index])
            if index == total - 1:
                self.hitboxes.append((px, self.TOP_Y, px + self.CARD_W,
                                      self.TOP_Y + self.CARD_H, "waste", index))

    def draw_foundations(self, hidden):
        for i in range(4):
            x = self.col_x(3 + i)
            pile_id = f"F{i}"
            cards = self.game.foundations[i].to_list()
            self.draw_slot(x, self.TOP_Y, "A")

            for index in range(max(0, len(cards) - 2), len(cards)):
                self.card_rects[(pile_id, index)] = (x, self.TOP_Y)
                if (pile_id, index) not in hidden:
                    self.draw_card(x, self.TOP_Y, cards[index])
            if cards:
                self.hitboxes.append((x, self.TOP_Y, x + self.CARD_W, self.TOP_Y + self.CARD_H,
                                      pile_id, len(cards) - 1))

    def draw_tableau(self, hidden):
        H = self.CARD_H
        free_height = self.CANVAS_H - self.TABLEAU_Y - H - 24

        for i in range(7):
            pile_id = f"T{i}"
            x = self.col_x(i)
            cards = self.game.tableau[i].to_list()
            self.draw_slot(x, self.TABLEAU_Y)


            down_gap, up_gap = 14.0, 32.0
            needed = sum(down_gap if not c.face_up else up_gap for c in cards[:-1])
            if needed > free_height:
                scale = free_height / needed
                down_gap *= scale
                up_gap *= scale

            y = self.TABLEAU_Y
            for index, card in enumerate(cards):
                self.card_rects[(pile_id, index)] = (x, y)
                if (pile_id, index) not in hidden:
                    self.draw_card(x, y, card)
                gap = down_gap if not card.face_up else up_gap
                is_last = index == len(cards) - 1
                click_height = H if is_last else gap
                self.hitboxes.append((x, y, x + self.CARD_W, y + click_height, pile_id, index))
                y += gap

    def draw_hint(self):
        W, H = self.CARD_W, self.CARD_H
        hint = self.hint
        areas = []

        if hint["kind"] == "draw":
            x = self.col_x(0)
            areas.append((x, self.TOP_Y, x + W, self.TOP_Y + H))
        else:
            pile = self.game.piles[hint["src"]]
            first = len(pile) - hint["count"]
            sx, sy = self.card_rects[(hint["src"], first)]
            ex, ey = self.card_rects[(hint["src"], len(pile) - 1)]
            areas.append((sx, sy, sx + W, ey + H))
            dx, dy = self.target_pos(hint["dst"])
            areas.append((dx, dy, dx + W, dy + H))

        for x1, y1, x2, y2 in areas:
            self.round_rect(x1 - 4, y1 - 4, x2 + 4, y2 + 4, 12, fill="", outline=self.PINK, width=8)
            self.round_rect(x1 - 4, y1 - 4, x2 + 4, y2 + 4, 12, fill="", outline="#fff0fa", width=3)

    def target_pos(self, dst):
        if dst.startswith("F"):
            return (self.col_x(3 + int(dst[1])), self.TOP_Y)
        pile = self.game.piles[dst]
        if pile.is_empty():
            return (self.col_x(int(dst[1])), self.TABLEAU_Y)
        return self.card_rects[(dst, len(pile) - 1)]


    def hit_test(self, x, y):
        for x1, y1, x2, y2, pile_id, index in reversed(self.hitboxes):
            if x1 <= x <= x2 and y1 <= y <= y2:
                return pile_id, index
        return None

    def on_press(self, e):
        if self.busy or self.game.won:
            return
        self.clear_hint(redraw=False)
        self.press = None

        hit = self.hit_test(e.x, e.y)
        if hit is None:
            return
        pile_id, index = hit

        if pile_id == "stock":
            self.do_draw()
            return


        cards = self.game.piles[pile_id].to_list()[index:]
        if not cards or not all(c.face_up for c in cards):
            return
        self.press = {
            "pid": pile_id, "idx": index, "count": len(cards),
            "x": e.x, "y": e.y,
            "lx": e.x, "ly": e.y,
            "dragging": False,
            "origins": [self.card_rects[(pile_id, i)] for i in range(index, index + len(cards))],
        }

    def on_motion(self, e):
        p = self.press
        if not p:
            return

        if not p["dragging"]:
            if abs(e.x - p["x"]) + abs(e.y - p["y"]) < 6:
                return

            p["dragging"] = True
            hidden = {(p["pid"], i) for i in range(p["idx"], p["idx"] + p["count"])}
            cards = self.game.piles[p["pid"]].to_list()[p["idx"]:]
            self.redraw(hidden)
            for (ox, oy), card in zip(p["origins"], cards):
                self.draw_card(ox, oy, card, tags=("drag",))
            p["lx"], p["ly"] = p["x"], p["y"]

        self.canvas.move("drag", e.x - p["lx"], e.y - p["ly"])
        p["lx"], p["ly"] = e.x, e.y

    def on_release(self, e):
        p = self.press
        self.press = None
        if not p:
            return
        if p["dragging"]:
            self.drop(p, e)
        else:
            self.handle_click(p)

    def drop(self, p, e):
        W, H = self.CARD_W, self.CARD_H
        src, count = p["pid"], p["count"]


        ox, oy = p["origins"][0]
        left = ox + e.x - p["x"]
        top = oy + e.y - p["y"]

        best, best_area = None, 0
        for dst in DEST_IDS:
            if dst == src or not self.game.can_move(src, dst, count):
                continue
            rx, ry = self.target_pos(dst)
            overlap_w = min(left + W, rx + W) - max(left, rx)
            overlap_h = min(top + H, ry + H) - max(top, ry)
            if overlap_w > 0 and overlap_h > 0 and overlap_w * overlap_h > best_area:
                best, best_area = dst, overlap_w * overlap_h


        if best and best_area >= 0.12 * W * H:
            self.game.move(src, best, count)
            self.after_action()
        else:
            self.redraw()
            self.set_status("That move is not allowed.")

    def handle_click(self, p):
        pile_id, index = p["pid"], p["idx"]
        now = time.time()
        is_top = index == len(self.game.piles[pile_id]) - 1

        previous = self.last_click
        self.last_click = (pile_id, index, now)
        is_double = (previous and previous[0] == pile_id and previous[1] == index
                     and now - previous[2] < 0.45)

        if is_double and is_top and not pile_id.startswith("F"):
            self.last_click = None
            for dst in FOUNDATION_IDS:
                if self.game.can_move(pile_id, dst, 1):
                    self.game.move(pile_id, dst, 1)
                    self.after_action()
                    return
            self.set_status("That card cannot go to a foundation yet.")


    def do_draw(self):
        recycling = self.game.stock.is_empty()
        if self.game.draw():
            self.after_action()
            self.set_status("Waste pile recycled into the stock." if recycling
                            else "Drew from the stock.")
        else:
            self.set_status("No cards left to draw.")

    def after_action(self):
        self.clear_hint(redraw=False)
        self.redraw()
        self.update_stats()
        if self.game.won:
            self.celebrate()

    def undo(self):
        if not self.busy and self.game.undo():
            self.after_action()
            self.set_status("Move undone.")

    def redo(self):
        if not self.busy and self.game.redo():
            self.after_action()
            self.set_status("Move redone.")

    def show_hint(self):
        if self.busy or self.game.won:
            return
        hint = self.game.find_hint()
        if hint is None:
            self.set_status("No moves available. Try undo or start a new game.")
            return
        self.clear_hint(redraw=False)
        self.hint = hint
        self.redraw()
        self.set_status("Hint: " + hint["text"])
        self.hint_job = self.root.after(2600, self.clear_hint)

    def clear_hint(self, redraw=True):
        if self.hint_job:
            self.root.after_cancel(self.hint_job)
            self.hint_job = None
        had_hint = self.hint is not None
        self.hint = None
        dragging = self.press and self.press["dragging"]
        if redraw and had_hint and not dragging:
            self.redraw()

    def auto_finish(self):
        if self.busy:
            return
        if not self.game.can_auto_finish():
            self.set_status("Auto Finish needs an empty stock and waste "
                            "with every tableau card face up.")
            return
        self.busy = True
        self.auto_step()

    def auto_step(self):
        moved = self.game.auto_finish_step()
        self.redraw()
        self.update_stats()
        if self.game.won:
            self.busy = False
            self.celebrate()
        elif moved:
            self.root.after(70, self.auto_step)
        else:
            self.busy = False
            self.update_stats()

    def toggle_draw(self):
        if self.busy:
            return
        g = self.game
        if not g.undo_stack.is_empty() and not g.won:
            if not messagebox.askyesno("Change Draw Mode",
                                       "Changing the draw mode starts a new game. Continue?"):
                return
        self.draw_count = 3 if self.draw_count == 1 else 1
        self.btn_draw.config(text=f"Draw: {self.draw_count}")
        self.new_game(False)

    def new_game(self, ask=True):
        if self.busy and not self.game.won:
            return
        g = self.game
        if ask and not g.undo_stack.is_empty() and not g.won:
            if not messagebox.askyesno("New Game",
                                       "Start a new game? Your current progress will be lost."):
                return
        self.stop_confetti()
        self.clear_hint(redraw=False)
        self.game = Game(self.draw_count)
        self.press = None
        self.last_click = None
        self.busy = False
        self.redraw()
        self.update_stats()
        self.set_status("New game started. Good luck!")


    def celebrate(self):
        self.busy = True
        self.update_stats()
        self.set_status("You won! Every card is on the foundation.")

        colors = [self.PINK, self.LIGHT_PINK, "#c77dff", "#9d4edd", "#ffffff", "#ff9ccc"]

        self.particles = [
            [random.uniform(0, self.CANVAS_W), random.uniform(-self.CANVAS_H, 0),
             random.uniform(-1.5, 1.5), random.uniform(2.5, 6.5),
             random.choice(colors), random.randint(5, 11)]
            for _ in range(150)
        ]
        self.confetti_frame = 0
        self.animate_confetti()

    def animate_confetti(self):
        c = self.canvas
        c.delete("confetti")
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            c.create_rectangle(p[0], p[1], p[0] + p[5], p[1] + p[5],
                               fill=p[4], outline="", tags="confetti")

        cx, cy = self.CANVAS_W / 2, self.CANVAS_H / 2
        c.create_text(cx + 3, cy + 3, text="YOU WIN!", fill="#2b0f4d",
                      font=("Georgia", 64, "bold"), tags="confetti")
        c.create_text(cx, cy, text="YOU WIN!", fill="#ffd1ea",
                      font=("Georgia", 64, "bold"), tags="confetti")

        self.confetti_frame += 1
        if self.confetti_frame < 140:
            self.confetti_job = self.root.after(30, self.animate_confetti)
        else:
            self.confetti_job = None
            self.finish_celebration()

    def stop_confetti(self):
        if self.confetti_job:
            self.root.after_cancel(self.confetti_job)
            self.confetti_job = None
        self.canvas.delete("confetti")

    def finish_celebration(self):
        g = self.game
        seconds = g.elapsed()
        again = messagebox.askyesno(
            "You Won!",
            f"Score: {g.score}  (time bonus {g.bonus})\n"
            f"Moves: {len(g.undo_stack)}\n"
            f"Time: {seconds // 60:02d}:{seconds % 60:02d}\n\nPlay again?",
        )
        self.busy = False
        if again:
            self.new_game(False)
        else:
            self.update_stats()


def blank_game(draw_count=1):
    g = Game(draw_count)
    for pile in g.piles.values():
        pile.clear()
    g.undo_stack.clear()
    g.redo_stack.clear()
    g.score = 0
    g.bonus = 0
    g.won = False
    g.start_time = None
    g.end_time = None
    g.refresh_positions()
    return g


def run_tests():
    results = []

    def check(name, condition):
        results.append(bool(condition))
        print(("PASS  " if condition else "FAIL  ") + name)

    random.seed(2026)


    deck = Deck()
    check("Deck holds 52 unique cards", len({c.key for c in deck.cards}) == 52 and len(deck) == 52)
    before_order = [c.key for c in deck.cards]
    deck.shuffle()
    check("Shuffle keeps all cards and changes the order",
          sorted(c.key for c in deck.cards) == sorted(before_order)
          and [c.key for c in deck.cards] != before_order)


    g = Game(1)
    check("Tableau piles are dealt with 1 to 7 cards", [len(p) for p in g.tableau] == [1, 2, 3, 4, 5, 6, 7])
    check("Only the last tableau card is face up",
          all([c.face_up for c in p.to_list()].count(True) == 1 and p.peek().face_up for p in g.tableau))
    check("Stock holds the remaining 24 cards face down",
          len(g.stock) == 24 and all(not c.face_up for c in g.stock.to_list()))
    check("Foundations and waste start empty",
          all(f.is_empty() for f in g.foundations) and g.waste.is_empty())
    check("Dictionary tracks all 52 card positions", len(g.positions) == 52)
    sample = g.tableau[3].get(2)
    info = g.find_card(sample.key)
    check("Dictionary reports pile index and face state correctly",
          info["pile"] == "T3" and info["index"] == 2 and info["face_up"] == sample.face_up)


    first = g.stock.peek()
    g.draw()
    check("Stock queue is FIFO and drawn card turns face up", g.waste.peek() is first and first.face_up)
    g3 = Game(3)
    order = g3.stock.peek_n(3)
    g3.draw()
    check("Draw three moves three cards in queue order",
          g3.waste.to_list() == order and len(g3.stock) == 21)

    g = blank_game()
    for i in range(24):
        g.stock.enqueue(Card("H", (i % 13) + 1))
    first_drawn = g.stock.peek()
    for _ in range(24):
        g.draw()
    check("Stock becomes empty after drawing everything", g.stock.is_empty() and len(g.waste) == 24)
    g.draw()
    check("Waste recycles back into the stock in the original order",
          len(g.stock) == 24 and g.stock.peek() is first_drawn and g.waste.is_empty())


    g = blank_game()
    g.tableau[0].push(Card("S", 7, True))
    g.tableau[1].push(Card("H", 6, True))
    g.tableau[2].push(Card("C", 6, True))
    g.tableau[3].push(Card("H", 5, True))
    g.tableau[4].push(Card("D", 13, True))
    check("Alternating color and descending rank is accepted", g.can_move("T1", "T0"))
    check("Same color is rejected", not g.can_move("T2", "T0"))
    check("Wrong rank is rejected", not g.can_move("T3", "T0"))
    check("Only a king may enter an empty column", g.can_move("T4", "T5") and not g.can_move("T1", "T5"))
    snap = g.snapshot()
    check("Illegal move returns False and leaves the state unchanged",
          g.move("T2", "T0") is False and g.snapshot() == snap)

    g = blank_game()
    g.tableau[1].push(Card("C", 9, True))
    g.tableau[1].push(Card("H", 8, True))
    g.tableau[2].push(Card("D", 10, True))
    check("A valid sequence of two cards can move together",
          g.move("T1", "T2", 2) and len(g.tableau[2]) == 3)
    g.tableau[3].push(Card("S", 4, True))
    g.tableau[3].push(Card("H", 3, False))
    check("A sequence containing a face down card cannot move", not g.can_move("T3", "T2", 2))


    g = blank_game()
    g.waste.push(Card("S", 1, True))
    check("Ace moves to an empty foundation", g.move("waste", "F0"))
    g.waste.push(Card("S", 2, True))
    check("Next rank of the same suit builds on the foundation", g.can_move("waste", "F0"))
    check("Another empty foundation rejects a non ace", not g.can_move("waste", "F1"))
    g.waste.push(Card("H", 2, True))
    check("Wrong suit cannot build on the foundation", not g.can_move("waste", "F0"))


    g = blank_game()
    g.tableau[0].push(Card("H", 3, False))
    g.tableau[0].push(Card("S", 4, True))
    g.tableau[1].push(Card("D", 5, True))
    original = g.snapshot()
    g.move("T0", "T1")
    check("Card flips face up after the card above it is moved", g.tableau[0].peek().face_up)
    check("Flipping a tableau card awards points", g.score == 5)
    g.undo()
    check("Undo restores the face down card and the score",
          not g.tableau[0].get(0).face_up and g.snapshot() == original)
    g.redo()
    check("Redo repeats the move and the flip", g.tableau[0].peek().face_up and g.score == 5)


    g = blank_game()
    for i, suit in enumerate(SUITS):
        for rank in range(1, 14):
            g.foundations[i].push(Card(suit, rank, True))
    check("Win is detected when all 52 cards are on the foundations", g.check_win() and g.is_won())

    g = blank_game()
    for i, suit in enumerate(SUITS):
        for rank in range(1, 14):
            if not (suit == "C" and rank == 13):
                g.foundations[i].push(Card(suit, rank, True))
    g.tableau[0].push(Card("C", 13, True))
    check("Win is not declared with 51 cards on the foundations", not g.check_win())
    check("Final king completes the game", g.move("T0", "F3") and g.won)


    random.seed(7)
    g = Game(1)
    start = g.snapshot()
    performed = 0
    for _ in range(40):
        hint = g.find_hint()
        if hint is None or g.won:
            break
        if hint["kind"] == "draw":
            g.draw()
        else:
            g.move(hint["src"], hint["dst"], hint["count"])
        performed += 1
        if sum(len(p) for p in g.piles.values()) != 52:
            break
    finish = g.snapshot()
    check("Game flow keeps exactly 52 cards in play", sum(len(p) for p in g.piles.values()) == 52)
    check("Positions dictionary matches the real piles after play",
          all(g.positions[c.key]["pile"] == pid for pid, p in g.piles.items() for c in p.to_list()))
    undone = 0
    while not g.undo_stack.is_empty() and not g.won:
        g.undo()
        undone += 1
    check("Undoing every move returns to the starting position", g.snapshot() == start and undone == performed)
    redone = 0
    while g.redo():
        redone += 1
    check("Redoing every move returns to the final position", g.snapshot() == finish and redone == performed)


    g = Game(1)
    for pile in g.piles.values():
        pile.clear()
    for i in range(4):
        for rank in range(1, 14):
            g.tableau[i].push(Card(SUITS[i], 14 - rank, True))
    check("Auto finish becomes available when everything is face up", g.can_auto_finish())
    guard = 0
    while not g.won and guard < 200:
        g.auto_finish_step()
        guard += 1
    check("Auto finish completes the game", g.won)

    passed = sum(results)
    print(f"\n{passed} of {len(results)} checks passed")
    return passed == len(results)


def main():
    if "--test" in sys.argv:
        sys.exit(0 if run_tests() else 1)
    root = tk.Tk()
    SolitaireApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()