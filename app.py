import random
import time
import tkinter as tk
from tkinter import messagebox

from cards import SUIT_SYMBOLS
from game import Game, FOUNDATION_IDS, DEST_IDS
from stats import load_stats, save_stats, record_result


class SolitaireApp:

    CARD_W = 100
    CARD_H = 140
    GAP = 20
    MARGIN = 40
    TOP_Y = 24
    TABLEAU_Y = 204
    CANVAS_W = 900
    CANVAS_H = 730


    TIME_LIMITS = (300, 600, 900, 1200)
    WARN = "#ff6b6b"

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
        self.time_limit = 600
        self.stats = load_stats()
        self.result_recorded = False
        self.game = Game(self.draw_count, self.time_limit)

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
        self.root.bind("<p>", lambda e: self.toggle_pause())
        self.root.bind("<P>", lambda e: self.toggle_pause())

        self.redraw()
        self.update_stats()
        self.set_status("Drag cards to move them. Click the stock to draw. "
                        "Double click a card to send it to the foundation. "
                        "The clock starts on your first move.")
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
            label = tk.Label(header, textvariable=var, bg=self.FELT, fg=self.LIGHT_PINK,
                             font=("Segoe UI", 11, "bold"), padx=12, pady=5)
            label.pack(side="right", padx=6, pady=10)
            if var is self.time_var:
                self.time_label = label


        bar = tk.Frame(self.root, bg=self.BG)
        bar.pack(fill="x", padx=14, pady=(8, 4))
        self.btn_new = self.make_button(bar, "New Game", lambda: self.new_game(True))
        self.btn_undo = self.make_button(bar, "Undo", self.undo)
        self.btn_redo = self.make_button(bar, "Redo", self.redo)
        self.btn_hint = self.make_button(bar, "Hint", self.show_hint)
        self.btn_auto = self.make_button(bar, "Auto Finish", self.auto_finish)
        self.btn_draw = self.make_button(bar, "Draw: 1", self.toggle_draw)
        self.btn_limit = self.make_button(bar, "Time: 10m", self.toggle_time_limit)
        self.btn_pause = self.make_button(bar, "Pause", self.toggle_pause)
        self.btn_stats = self.make_button(bar, "Stats", self.show_stats)


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
                           padx=10, pady=7, font=("Segoe UI", 10, "bold"), cursor="hand2")
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

    def refresh_clock(self):
        g = self.game
        left = g.time_left()
        self.time_var.set(f"Time Left  {left // 60:02d}:{left % 60:02d}")
        warning = g.start_time is not None and left <= 60 and not g.won
        self.time_label.config(fg=self.WARN if warning else self.LIGHT_PINK)

    def update_stats(self):
        g = self.game
        self.refresh_clock()
        self.moves_var.set(f"Moves  {len(g.undo_stack)}")
        self.score_var.set(f"Score  {g.score}")

        idle = not g.won and not g.lost and not g.paused and not self.busy
        self.set_enabled(self.btn_undo, idle and not g.undo_stack.is_empty())
        self.set_enabled(self.btn_redo, idle and not g.redo_stack.is_empty())
        self.set_enabled(self.btn_hint, idle)
        self.set_enabled(self.btn_auto, not self.busy and g.can_auto_finish())
        can_pause = not g.won and not g.lost and not self.busy and g.start_time is not None
        self.set_enabled(self.btn_pause, can_pause)
        self.btn_pause.config(text="Resume" if g.paused else "Pause")

    def tick(self):
        self.refresh_clock()
        self.check_game_over()
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

        if self.game.paused:
            self.draw_overlay("PAUSED", "Press Resume or P to continue")
            return

        self.draw_stock()
        self.draw_waste(hidden)
        self.draw_foundations(hidden)
        self.draw_tableau(hidden)
        if self.hint:
            self.draw_hint()
        if self.game.lost:
            self.draw_overlay("TIME'S UP!", "Game over. Start a new game to play again.")

    def draw_overlay(self, title, subtitle):
        cx, cy = self.CANVAS_W / 2, self.CANVAS_H / 2
        self.round_rect(cx - 330, cy - 90, cx + 330, cy + 90, 20, fill=self.DEEP,
                        outline=self.PINK, width=4)
        self.canvas.create_text(cx, cy - 20, text=title, fill=self.LIGHT_PINK,
                                font=("Georgia", 48, "bold"))
        self.canvas.create_text(cx, cy + 45, text=subtitle, fill=self.LIGHT_PINK,
                                font=("Segoe UI", 12, "bold"))

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
        if self.busy or self.game.won or self.game.lost or self.game.paused:
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
        else:
            self.check_game_over()

    def undo(self):
        if not self.busy and self.game.undo():
            self.after_action()
            self.set_status("Move undone.")

    def redo(self):
        if not self.busy and self.game.redo():
            self.after_action()
            self.set_status("Move redone.")

    def show_hint(self):
        if self.busy or self.game.won or self.game.lost or self.game.paused:
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
        if not g.undo_stack.is_empty() and not g.won and not g.lost:
            if not messagebox.askyesno("Change Draw Mode",
                                       "Changing the draw mode starts a new game. Continue?"):
                return
        self.draw_count = 3 if self.draw_count == 1 else 1
        self.btn_draw.config(text=f"Draw: {self.draw_count}")
        self.new_game(False)

    def check_game_over(self):
        if not self.game.check_time() or self.result_recorded:
            return
        self.store_result(False)
        self.press = None
        self.clear_hint(redraw=False)
        self.redraw()
        self.update_stats()
        self.set_status("Time is up. You lost this game.")
        self.root.after(200, self.show_loss_dialog)

    def store_result(self, won):
        if self.result_recorded:
            return
        self.result_recorded = True
        g = self.game
        record_result(self.stats, won, g.score, g.elapsed())
        save_stats(self.stats)

    def show_loss_dialog(self):
        g = self.game
        if not g.lost:
            return
        on_foundations = sum(len(f) for f in g.foundations)
        again = messagebox.askyesno(
            "Time's Up!",
            f"You ran out of time and lost the game.\n\nScore: {g.score}\n"
            f"Moves: {len(g.undo_stack)}\n"
            f"Cards on foundations: {on_foundations} of 52\n\nPlay again?",
        )
        if again:
            self.new_game(False)
        else:
            self.update_stats()

    def toggle_pause(self):
        g = self.game
        if self.busy or g.won or g.lost:
            return
        if g.start_time is None:
            self.set_status("The clock starts on your first move, so there is nothing to pause yet.")
            return
        self.clear_hint(redraw=False)
        self.press = None
        g.toggle_pause()
        self.redraw()
        self.update_stats()
        self.set_status("Game paused. Press Resume or P to continue." if g.paused
                        else "Game resumed.")

    def toggle_time_limit(self):
        if self.busy:
            return
        g = self.game
        if not g.undo_stack.is_empty() and not g.won and not g.lost:
            if not messagebox.askyesno("Change Time Limit",
                                       "Changing the time limit starts a new game. Continue?"):
                return
        position = self.TIME_LIMITS.index(self.time_limit)
        self.time_limit = self.TIME_LIMITS[(position + 1) % len(self.TIME_LIMITS)]
        self.btn_limit.config(text=f"Time: {self.time_limit // 60}m")
        self.new_game(False)

    def show_stats(self):
        s = self.stats
        played = s["played"]
        win_rate = f"{100 * s['won'] // played}%" if played else "0%"
        best = s["best_time"]
        best_time = f"{best // 60:02d}:{best % 60:02d}" if best is not None else "none yet"
        messagebox.showinfo(
            "Statistics",
            f"Games played: {played}\nWon: {s['won']}\nLost: {s['lost']}\n"
            f"Win rate: {win_rate}\nBest score: {s['best_score']}\nFastest win: {best_time}",
        )

    def new_game(self, ask=True):
        if self.busy and not self.game.won:
            return
        g = self.game
        if ask and not g.undo_stack.is_empty() and not g.won and not g.lost:
            if not messagebox.askyesno("New Game",
                                       "Start a new game? Your current progress will be lost."):
                return
        self.stop_confetti()
        self.clear_hint(redraw=False)
        self.game = Game(self.draw_count, self.time_limit)
        self.result_recorded = False
        self.press = None
        self.last_click = None
        self.busy = False
        self.redraw()
        self.update_stats()
        self.set_status("New game started. Good luck!")


    def celebrate(self):
        self.busy = True
        self.store_result(True)
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
