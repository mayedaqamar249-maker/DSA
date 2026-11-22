import os
import random
import tempfile
import time

from cards import Card, Deck, SUITS
from game import Game
from stats import empty_stats, load_stats, record_result, save_stats


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

    g = blank_game()
    check("Time limit defaults to 10 minutes", g.time_limit == 600 and g.time_left() == 600)
    check("Clock does not start before the first move", g.start_time is None and g.elapsed() == 0)
    check("Time limit can be chosen when creating a game", Game(1, 120).time_limit == 120)

    g = blank_game()
    g.time_limit = 60
    g.waste.push(Card("S", 1, True))
    g.start_time = time.time() - 61
    check("Game is lost when the time limit runs out", g.check_time() and g.lost and g.time_left() == 0)
    check("No moves are allowed after time is up", not g.move("waste", "F0") and not g.draw())
    check("Undo and redo are blocked after time is up", not g.undo() and not g.redo())
    check("Auto finish is blocked after time is up", not g.can_auto_finish())

    g = blank_game()
    g.time_limit = 60
    g.start_time = time.time() - 30
    check("Game is not lost while time remains", not g.check_time() and 28 <= g.time_left() <= 30)

    g = blank_game()
    for i, suit in enumerate(SUITS):
        for rank in range(1, 14):
            if not (suit == "C" and rank == 13):
                g.foundations[i].push(Card(suit, rank, True))
    g.tableau[0].push(Card("C", 13, True))
    g.start_time = time.time() - 100
    check("Winning before time runs out counts as a win",
          g.move("T0", "F3") and g.won and not g.lost and g.bonus > 0)

    g = blank_game()
    g.waste.push(Card("S", 1, True))
    check("Pause needs a started game", not g.pause())
    g.start_time = time.time() - 20
    check("Pause works once the clock is running", g.pause() and g.paused)
    check("No moves are allowed while paused", not g.move("waste", "F0") and not g.undo())
    frozen = g.elapsed()
    check("Clock is frozen while paused", g.elapsed() == frozen)
    g.pause_started = time.time() - 10
    check("Resume restarts the clock", g.resume() and not g.paused)
    check("Paused time is not counted", 9 <= g.elapsed() <= 10)
    check("Moves work again after resume", g.move("waste", "F0"))

    stats = empty_stats()
    record_result(stats, True, 500, 200)
    record_result(stats, False, 120, 600)
    record_result(stats, True, 400, 150)
    check("Stats count games played, won and lost",
          stats["played"] == 3 and stats["won"] == 2 and stats["lost"] == 1)
    check("Stats keep the best score and fastest win", stats["best_score"] == 500 and stats["best_time"] == 150)
    path = os.path.join(tempfile.mkdtemp(), "stats.json")
    save_stats(stats, path)
    check("Stats are saved to and loaded from a file", load_stats(path) == stats)
    check("A missing stats file gives empty stats", load_stats(path + ".missing") == empty_stats())

    passed = sum(results)
    print(f"\n{passed} of {len(results)} checks passed")
    return passed == len(results)
