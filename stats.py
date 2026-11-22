import json
import os


STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "solitaire_stats.json")


def empty_stats():
    return {"played": 0, "won": 0, "lost": 0, "best_score": 0, "best_time": None}


def load_stats(path=STATS_FILE):
    stats = empty_stats()
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for key in stats:
            if key in saved:
                stats[key] = saved[key]
    except (OSError, ValueError, TypeError):
        pass
    return stats


def save_stats(stats, path=STATS_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats, f)
    except OSError:
        pass


def record_result(stats, won, score, seconds):
    stats["played"] += 1
    stats["best_score"] = max(stats["best_score"], score)
    if won:
        stats["won"] += 1
        best = stats["best_time"]
        if best is None or seconds < best:
            stats["best_time"] = seconds
    else:
        stats["lost"] += 1
    return stats
