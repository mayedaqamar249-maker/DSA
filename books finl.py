import csv
import hashlib
import html
import json
import math
import os
import random
import re
import sys
import threading
import time
import webbrowser
import zlib
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PyQt5.QtCore import (
    Qt, QThread, QObject, QTimer, QSize, QAbstractTableModel,
    QModelIndex, QUrl, pyqtSignal
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QLinearGradient, QPalette
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFormLayout, QLineEdit, QTextEdit, QPushButton,
    QTableView, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QLabel, QComboBox, QSpinBox, QCheckBox,
    QProgressBar, QGroupBox, QFrame, QScrollArea, QDialog,
    QDialogButtonBox, QTabWidget, QSizePolicy
)

# PyQtWebEngine is required to show Folium maps inside the application.
# Install it in the same Python environment used to run this file:
# python -m pip install PyQtWebEngine
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings


try:
    import lxml
    PARSER = "lxml"
except ImportError:
    PARSER = "html.parser"


try:
    APP_DIR = Path(__file__).resolve().parent
except NameError:
    APP_DIR = Path.cwd()

CSV_FILE = APP_DIR / "books.csv"
COVER_DIR = APP_DIR / "covers"
MAP_FILE = APP_DIR / "books_map.html"

HTTP_HEADERS = {
    "User-Agent": "CS200-BooksProject/1.0 (student project; polite crawler)"
}

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FETCH_ERRORS = {}
SCRAPE_THREADS = 10
SCRAPE_DELAY = 0.1
SAVE_EVERY = 1000
GUTENBERG_MAX_ID = 80000
MAP_MARKER_LIMIT = 3000
CRAWL_MAX_PAGES = 300

FIELDS = [
    "title", "author", "genre", "language", "release_year", "downloads",
    "price", "rating", "availability", "description", "cover_url",
    "source_url", "latitude", "longitude"
]
HEADERS = [
    "Title", "Author", "Genre", "Language", "Release Year", "Downloads",
    "Price", "Rating", "Availability", "Description", "Cover URL",
    "Source URL", "Latitude", "Longitude"
]
NUMERIC = {
    "release_year", "downloads", "price", "rating", "latitude", "longitude"
}
COLUMN_WIDTHS = {
    "title": 260, "author": 170, "genre": 130, "language": 90,
    "release_year": 115, "downloads": 105, "price": 75, "rating": 75,
    "availability": 120, "description": 300, "cover_url": 200,
    "source_url": 250, "latitude": 80, "longitude": 80
}

TEXT_OPS = ["contains", "equals", "starts with", "ends with",
            "not contains", "regex"]
NUM_OPS = ["=", "!=", ">", ">=", "<", "<="]


LANG_LOCATIONS = {
    "English": ("London", 51.5074, -0.1278),
    "French": ("Paris", 48.8566, 2.3522),
    "German": ("Berlin", 52.5200, 13.4050),
    "Spanish": ("Madrid", 40.4168, -3.7038),
    "Italian": ("Rome", 41.9028, 12.4964),
    "Latin": ("Rome", 41.9028, 12.4964),
    "Finnish": ("Helsinki", 60.1699, 24.9384),
    "Dutch": ("Amsterdam", 52.3676, 4.9041),
    "Portuguese": ("Lisbon", 38.7223, -9.1393),
    "Chinese": ("Beijing", 39.9042, 116.4074),
    "Japanese": ("Tokyo", 35.6762, 139.6503),
    "Greek": ("Athens", 37.9838, 23.7275),
    "Swedish": ("Stockholm", 59.3293, 18.0686),
    "Danish": ("Copenhagen", 55.6761, 12.5683),
    "Norwegian": ("Oslo", 59.9139, 10.7522),
    "Hungarian": ("Budapest", 47.4979, 19.0402),
    "Polish": ("Warsaw", 52.2297, 21.0122),
    "Russian": ("Moscow", 55.7558, 37.6173),
    "Czech": ("Prague", 50.0755, 14.4378),
    "Catalan": ("Barcelona", 41.3874, 2.1686),
    "Welsh": ("Cardiff", 51.4816, -3.1791),
    "Tagalog": ("Manila", 14.5995, 120.9842),
    "Arabic": ("Cairo", 30.0444, 31.2357),
    "Hebrew": ("Jerusalem", 31.7683, 35.2137),
    "Urdu": ("Lahore", 31.5204, 74.3587),
    "Hindi": ("Delhi", 28.6139, 77.2090),
    "Esperanto": ("Warsaw", 52.2297, 21.0122),
}

LANG_NAMES = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
    "zh": "Chinese", "ja": "Japanese", "ar": "Arabic", "ur": "Urdu",
    "hi": "Hindi", "sv": "Swedish", "da": "Danish", "no": "Norwegian",
    "nb": "Norwegian", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
    "hu": "Hungarian", "el": "Greek", "he": "Hebrew", "la": "Latin",
    "ca": "Catalan", "cy": "Welsh", "tl": "Tagalog", "eo": "Esperanto",
}


def location_for(language, seed_text=""):
    info = LANG_LOCATIONS.get((language or "").strip())
    if not info:
        return "", ""
    h = zlib.crc32(seed_text.encode("utf-8"))
    dlat = ((h & 0xFFFF) / 65535 - 0.5) * 0.8
    dlon = (((h >> 16) & 0xFFFF) / 65535 - 0.5) * 0.8
    return f"{info[1] + dlat:.4f}", f"{info[2] + dlon:.4f}"


def new_book(**kw):
    book = {f: "" for f in FIELDS}
    for key, value in kw.items():
        if key in book:
            book[key] = "" if value is None else str(value)
    if not book["latitude"] or not book["longitude"]:
        lat, lon = location_for(
            book["language"], book["title"] + book["source_url"]
        )
        book["latitude"], book["longitude"] = lat, lon
    return book


def read_csv_file(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        return [
            {f: (row.get(f) or "") for f in FIELDS} for row in reader
        ]


def _dump_csv(path, books):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(books)


def write_csv_file(path, books):
    tmp = Path(str(path) + ".tmp")
    try:
        _dump_csv(tmp, books)
        os.replace(tmp, path)
    except PermissionError:

        try:
            _dump_csv(path, books)
        except PermissionError:
            raise OSError(
                f"Cannot write {Path(path).name}. It is probably open in "
                "Excel or another program. Close it and the app will save "
                "again automatically."
            )
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass


def load_books():
    if not CSV_FILE.exists():
        return []
    try:
        return read_csv_file(CSV_FILE)
    except (OSError, csv.Error):
        return []


def save_books(books):
    write_csv_file(CSV_FILE, books)


class Stats:
    __slots__ = ("cmp", "swap")

    def __init__(self):
        self.cmp = 0
        self.swap = 0


def bubble_sort(a, cmp, st):
    n = len(a)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if cmp(a[j], a[j + 1]) > 0:
                a[j], a[j + 1] = a[j + 1], a[j]
                st.swap += 1
                swapped = True
        if not swapped:
            break


def selection_sort(a, cmp, st):
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            if cmp(a[j], a[m]) < 0:
                m = j
        if m != i:
            a[i], a[m] = a[m], a[i]
            st.swap += 1


def insertion_sort(a, cmp, st):
    for i in range(1, len(a)):
        cur = a[i]
        j = i - 1
        while j >= 0 and cmp(a[j], cur) > 0:
            a[j + 1] = a[j]
            st.swap += 1
            j -= 1
        a[j + 1] = cur


def merge_sort(a, cmp, st):
    n = len(a)
    if n < 2:
        return
    aux = a[:]

    def rec(lo, hi):
        if hi - lo < 2:
            return
        mid = (lo + hi) // 2
        rec(lo, mid)
        rec(mid, hi)
        aux[lo:hi] = a[lo:hi]
        i, j, k = lo, mid, lo
        while i < mid and j < hi:
            if cmp(aux[j], aux[i]) < 0:
                a[k] = aux[j]
                j += 1
            else:
                a[k] = aux[i]
                i += 1
            k += 1
            st.swap += 1
        while i < mid:
            a[k] = aux[i]
            i += 1
            k += 1
            st.swap += 1
        while j < hi:
            a[k] = aux[j]
            j += 1
            k += 1
            st.swap += 1

    rec(0, n)


def quick_sort(a, cmp, st):
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            pivot = a[(lo + hi) // 2]
            i, j = lo, hi
            while i <= j:
                while cmp(a[i], pivot) < 0:
                    i += 1
                while cmp(a[j], pivot) > 0:
                    j -= 1
                if i <= j:
                    if i != j:
                        a[i], a[j] = a[j], a[i]
                        st.swap += 1
                    i += 1
                    j -= 1
            if j - lo < hi - i:
                stack.append((i, hi))
                hi = j
            else:
                stack.append((lo, j))
                lo = i


def heap_sort(a, cmp, st):
    n = len(a)

    def sift(i, size):
        while True:
            left = 2 * i + 1
            if left >= size:
                return
            big = left
            if left + 1 < size and cmp(a[left + 1], a[left]) > 0:
                big = left + 1
            if cmp(a[big], a[i]) <= 0:
                return
            a[i], a[big] = a[big], a[i]
            st.swap += 1
            i = big

    for i in range(n // 2 - 1, -1, -1):
        sift(i, n)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        st.swap += 1
        sift(0, end)


def shell_sort(a, cmp, st):
    n = len(a)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            cur = a[i]
            j = i
            while j >= gap and cmp(a[j - gap], cur) > 0:
                a[j] = a[j - gap]
                st.swap += 1
                j -= gap
            a[j] = cur
        gap //= 2


def cocktail_sort(a, cmp, st):
    lo, hi = 0, len(a) - 1
    swapped = True
    while swapped:
        swapped = False
        for i in range(lo, hi):
            if cmp(a[i], a[i + 1]) > 0:
                a[i], a[i + 1] = a[i + 1], a[i]
                st.swap += 1
                swapped = True
        if not swapped:
            break
        hi -= 1
        swapped = False
        for i in range(hi, lo, -1):
            if cmp(a[i - 1], a[i]) > 0:
                a[i - 1], a[i] = a[i], a[i - 1]
                st.swap += 1
                swapped = True
        lo += 1


ALGORITHMS = {
    "Bubble": dict(fn=bubble_sort, best="O(n)", avg="O(n^2)",
                   worst="O(n^2)", space="O(1)", stable=True),
    "Selection": dict(fn=selection_sort, best="O(n^2)", avg="O(n^2)",
                      worst="O(n^2)", space="O(1)", stable=False),
    "Insertion": dict(fn=insertion_sort, best="O(n)", avg="O(n^2)",
                      worst="O(n^2)", space="O(1)", stable=True),
    "Merge": dict(fn=merge_sort, best="O(n log n)", avg="O(n log n)",
                  worst="O(n log n)", space="O(n)", stable=True),
    "Quick": dict(fn=quick_sort, best="O(n log n)", avg="O(n log n)",
                  worst="O(n^2)", space="O(log n)", stable=False),
    "Heap": dict(fn=heap_sort, best="O(n log n)", avg="O(n log n)",
                 worst="O(n log n)", space="O(1)", stable=False),
    "Shell": dict(fn=shell_sort, best="O(n log n)", avg="O(n^1.5)",
                  worst="O(n^2)", space="O(1)", stable=False),
    "Cocktail": dict(fn=cocktail_sort, best="O(n)", avg="O(n^2)",
                     worst="O(n^2)", space="O(1)", stable=True),
}
QUADRATIC = {"Bubble", "Selection", "Insertion", "Cocktail"}


def complexity_text(name):
    info = ALGORITHMS[name]
    return (f"Best {info['best']} | Avg {info['avg']} | "
            f"Worst {info['worst']} | Space {info['space']} | "
            f"{'Stable' if info['stable'] else 'Not stable'}")


def key_for(field, value):
    """Sortable key. Blank values get (1, ...) so they always sort last."""
    value = (value or "").strip()
    if field in NUMERIC:
        try:
            return (0, float(value))
        except ValueError:
            return (1, 0.0)
    if not value:
        return (1, "")
    return (0, value.casefold())


def make_cmp(descs):
    count = len(descs)

    def cmp(a, b):
        ka, kb = a[0], b[0]
        for i in range(count):
            x, y = ka[i], kb[i]
            if x == y:
                continue
            if x[0] != y[0]:
                return -1 if x[0] < y[0] else 1
            r = -1 if x < y else 1
            return -r if descs[i] else r
        return 0

    return cmp


def run_sort(rows, levels, algo_name):
    """levels is a list of (field, descending). Returns rows, ms, cmps, swaps."""
    fn = ALGORITHMS[algo_name]["fn"]
    items = [
        (tuple(key_for(f, r.get(f, "")) for f, _ in levels), r)
        for r in rows
    ]
    st = Stats()
    base = make_cmp([d for _, d in levels])

    def cmp(a, b):
        st.cmp += 1
        return base(a, b)

    start = time.perf_counter()
    fn(items, cmp, st)
    ms = (time.perf_counter() - start) * 1000
    return [r for _, r in items], ms, st.cmp, st.swap


def run_benchmark(rows, levels):
    results = []
    for name in ALGORITHMS:
        _, ms, comps, swaps = run_sort(rows, levels, name)
        results.append(dict(name=name, ms=ms, cmp=comps, swap=swaps))
    return results


def matches(book, field, op, value):
    raw = str(book.get(field, ""))
    if field in NUMERIC:
        try:
            x = float(raw)
            v = float(value)
        except ValueError:
            return False
        if op == "=":
            return x == v
        if op == "!=":
            return x != v
        if op == ">":
            return x > v
        if op == ">=":
            return x >= v
        if op == "<":
            return x < v
        if op == "<=":
            return x <= v
        return False
    s = raw.casefold()
    v = value.casefold()
    if op == "contains":
        return v in s
    if op == "equals":
        return s == v
    if op == "starts with":
        return s.startswith(v)
    if op == "ends with":
        return s.endswith(v)
    if op == "not contains":
        return v not in s
    if op == "regex":
        try:
            return re.search(value, raw, re.IGNORECASE) is not None
        except re.error:
            return False
    return False


def evaluate_conditions(book, conditions):
    """Left to right evaluation of (join, negate, field, op, value)."""
    result = None
    for join, negate, field, op, value in conditions:
        hit = matches(book, field, op, value)
        if negate:
            hit = not hit
        if result is None:
            result = hit
        elif join == "AND":
            result = result and hit
        else:
            result = result or hit
    return bool(result)


def binary_lower_bound(keys, target):
    lo, hi, comps = 0, len(keys), 0
    while lo < hi:
        mid = (lo + hi) // 2
        comps += 1
        if keys[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo, comps


def jump_lower_bound(keys, target):
    n = len(keys)
    step = max(1, int(math.sqrt(n)))
    prev, comps = 0, 0
    while prev < n:
        comps += 1
        if keys[min(prev + step, n) - 1] < target:
            prev += step
        else:
            break
    i = prev
    while i < n and keys[i] < target:
        comps += 1
        i += 1
    return i, comps


SORTED_OPS = {"equals", "starts with", "="}
SEARCH_ALGOS = {
    "Linear Search": "O(n) | works on unsorted data",
    "Binary Search": "O(log n) | needs sorted data (sorted first) | equals and starts with",
    "Jump Search": "O(sqrt n) | needs sorted data (sorted first) | equals and starts with",
}


def search_column(rows, field, op, value, algo):
    """Returns (results, comparisons, prep_ms, algorithm_used)."""
    if algo == "Linear Search" or op not in SORTED_OPS or not rows:
        used = "Linear Search"
        if algo != "Linear Search":
            used = "Linear Search (fallback, operator needs it)"
        return ([b for b in rows if matches(b, field, op, value)],
                len(rows), 0.0, used)

    if field in NUMERIC:
        try:
            target = (0, float(value))
        except ValueError:
            return [], 0, 0.0, algo
    else:
        target = (0, value.strip().casefold())

    t0 = time.perf_counter()
    keyed = sorted(
        ((key_for(field, b.get(field, "")), b) for b in rows),
        key=lambda t: t[0]
    )
    prep = (time.perf_counter() - t0) * 1000
    keys = [k for k, _ in keyed]

    if algo == "Binary Search":
        index, comps = binary_lower_bound(keys, target)
    else:
        index, comps = jump_lower_bound(keys, target)

    prefix = op == "starts with"
    out = []
    while index < len(keys):
        k = keys[index]
        if k[0] != 0:
            break
        ok = k[1].startswith(target[1]) if prefix else k == target
        if not ok:
            break
        out.append(keyed[index][1])
        index += 1
    return out, comps + len(out), prep, algo


_local = threading.local()


def get_session():
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(HTTP_HEADERS)
        _local.session = session
    return session


def fetch(url, retries=3, browser=False):
    """Download a page. Returns text or None (reason kept in FETCH_ERRORS)."""
    session = get_session()
    headers = BROWSER_HEADERS if browser else None
    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=(5, 12))
            if r.status_code == 404:
                FETCH_ERRORS[url] = "HTTP 404, page not found"
                return None
            if r.status_code in (401, 403):
                FETCH_ERRORS[url] = (
                    f"HTTP {r.status_code}, the site blocked the request "
                    "(bot protection or login needed)"
                )
                return None
            if r.status_code in (429, 503):
                FETCH_ERRORS[url] = f"HTTP {r.status_code}, site is busy or blocking"
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").lower()
            if ctype and not any(k in ctype for k in
                                 ("html", "json", "xml", "text")):
                FETCH_ERRORS[url] = "that link is a file, not a web page"
                return None
            if "charset" not in ctype:
                r.encoding = "utf-8"
            return r.text
        except requests.RequestException as error:
            FETCH_ERRORS[url] = str(error)[:120]
            time.sleep(0.5)
    return None


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class CrawlUrl(str):
    """A link found while crawling a listing page. It must look like a
    book/product/article page before it is accepted (strict mode)."""


def norm_url(url):
    """Normalise a URL so the same page is not saved twice."""
    url = (url or "").strip().split("#")[0]
    p = urlparse(url)
    out = f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}"
    return out + (f"?{p.query}" if p.query else "")


def site_of(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def parse_gutenberg(page, url):
    soup = BeautifulSoup(page, PARSER)
    table = soup.find("table", class_="bibrec")
    if table is None:
        return None
    info = {}
    for tr in table.find_all("tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            info.setdefault(clean(th.get_text()), []).append(
                clean(td.get_text(" "))
            )

    title = (info.get("Title") or [""])[0]
    if not title:
        return None

    author = (info.get("Author") or ["Unknown"])[0]
    author = re.sub(r",?\s*\(?\b\d{3,4}\b.*$", "", author).strip(", ")
    author = author or "Unknown"

    subjects = info.get("Subject") or info.get("Category") or [""]
    genre = subjects[0].split(" -- ")[-1].strip()

    year = ""
    m = re.search(r"(\d{4})", (info.get("Release Date") or [""])[0])
    if m:
        year = m.group(1)

    downloads = ""
    m = re.search(r"[\d,]+", (info.get("Downloads") or [""])[0])
    if m:
        downloads = m.group(0).replace(",", "")

    summary = " ".join(info.get("Summary") or [])
    summary = summary.replace("(This is an automatically generated summary.)", "")
    summary = clean(summary)[:600]

    cover = ""
    img = soup.find("img", class_="cover-art")
    if img and img.get("src"):
        cover = urljoin(url, img["src"])

    return new_book(
        title=title, author=author, genre=genre,
        language=(info.get("Language") or [""])[0],
        release_year=year, downloads=downloads, price="0",
        availability="Free download", description=summary,
        cover_url=cover, source_url=url
    )


RATING_WORDS = {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}


def parse_toscrape(page, url):
    soup = BeautifulSoup(page, PARSER)
    main = soup.select_one("div.product_main")
    if main is None or main.h1 is None:
        return None
    title = clean(main.h1.get_text())

    price = ""
    tag = main.select_one("p.price_color")
    if tag:
        price = re.sub(r"[^\d.]", "", tag.get_text())

    rating = ""
    tag = main.select_one("p.star-rating")
    if tag and tag.get("class"):
        rating = RATING_WORDS.get(tag["class"][-1], "")

    avail = ""
    tag = main.select_one("p.availability")
    if tag:
        avail = clean(tag.get_text(" "))

    crumbs = soup.select("ul.breadcrumb li")
    genre = clean(crumbs[2].get_text()) if len(crumbs) > 2 else ""

    desc = ""
    box = soup.select_one("#product_description")
    if box:
        p = box.find_next_sibling("p")
        if p:
            desc = clean(p.get_text(" "))

    cover = ""
    img = soup.select_one("#product_gallery img")
    if img and img.get("src"):
        cover = urljoin(url, img["src"])

    return new_book(
        title=title, author="Unknown", genre=genre, language="English",
        price=price, rating=rating, availability=avail, description=desc,
        cover_url=cover, source_url=url
    )


# ---- generic websites (Custom URL) -----------------------------------------
DETAIL_LD = {"Book", "Product", "Audiobook", "Article", "BlogPosting",
             "NewsArticle", "CreativeWork", "Periodical"}
BOOK_LD = {"Book", "Product", "Audiobook"}
DETAIL_OG = {"book", "books.book", "article", "product", "og:product",
             "product.item"}
SKIP_PATH = re.compile(
    r"/(tag|tags|category|categories|product-category|author|authors|page|"
    r"search|login|register|cart|checkout|my-account|contact|about|privacy|"
    r"terms|dmca|feed|wp-admin|wp-login|wp-json|wp-content|cdn-cgi)(/|$)"
    r"|\.(jpe?g|png|gif|webp|svg|pdf|css|js|zip|xml|ico)$",
    re.IGNORECASE
)
LISTING_SELECTORS = [
    "article a[href]", ".entry-title a[href]", "li.product a[href]",
    ".product a[href]", ".post a[href]", ".book a[href]",
    "h1 a[href]", "h2 a[href]", "h3 a[href]", "h4 a[href]",
]
NEXT_SELECTORS = [
    'link[rel="next"]', 'a[rel~="next"]', "a.next", "li.next a",
    ".pagination .next a", ".nav-previous a",
]


def language_name(raw):
    raw = clean(str(raw or ""))
    code = re.split(r"[-_]", raw)[0].lower()
    if code in LANG_NAMES:
        return LANG_NAMES[code]
    if len(raw) > 3 and raw.isalpha():
        return raw.title()
    return ""


def ld_types(d):
    t = d.get("@type", [])
    if isinstance(t, str):
        t = [t]
    return {str(x) for x in t} if isinstance(t, list) else set()


def jsonld_items(soup):
    """All JSON-LD objects on the page (flattened, including @graph)."""
    items, stack = [], []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            stack.append(json.loads(tag.string or tag.get_text() or ""))
        except ValueError:
            continue
    while stack:
        d = stack.pop()
        if isinstance(d, list):
            stack.extend(d)
        elif isinstance(d, dict):
            items.append(d)
            if d.get("@graph"):
                stack.append(d["@graph"])
    return items


def ld_text(value):
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("name") or value.get("url") or value.get("@id") or ""
    return clean(str(value)) if value else ""


def ld_names(value, limit=2):
    if not isinstance(value, list):
        value = [value]
    names = [ld_text(v) for v in value if v]
    return ", ".join([n for n in names if n][:limit])


def strip_site_suffix(title, site_name, url):
    """'Book Title - SiteName' -> 'Book Title'."""
    label = site_of(url).split(".")[0]
    for sep in (" | ", " - ", " \u2013 ", " \u2014 ", " :: "):
        if sep in title:
            head, tail = title.rsplit(sep, 1)
            t = tail.strip().lower()
            same_site = bool(site_name) and t == site_name.strip().lower()
            has_label = len(label) >= 4 and label in t.replace(" ", "")
            if head.strip() and (same_site or has_label):
                return head.strip()
    return title


def page_is_detail(soup):
    og = soup.find("meta", attrs={"property": "og:type"})
    if og and clean(og.get("content", "")).lower() in DETAIL_OG:
        return True
    return any(ld_types(d) & DETAIL_LD for d in jsonld_items(soup))


def parse_generic(page, url, strict=False):
    """Read book info from any web page: JSON-LD first, then meta tags,
    then plain HTML. strict=True (crawled links) rejects non-book pages."""
    soup = BeautifulSoup(page, PARSER)
    items = jsonld_items(soup)
    ld = (next((d for d in items if ld_types(d) & BOOK_LD), None)
          or next((d for d in items if ld_types(d) & DETAIL_LD), None)
          or {})

    def meta(*names):
        for name in names:
            tag = (soup.find("meta", attrs={"property": name})
                   or soup.find("meta", attrs={"name": name}))
            if tag and tag.get("content"):
                return clean(tag["content"])
        return ""

    if strict and not (ld or meta("og:type").lower() in DETAIL_OG):
        return None

    title = ld_text(ld.get("name") or ld.get("headline")) \
        or meta("og:title", "twitter:title")
    if not title and soup.title:
        title = clean(soup.title.get_text())
    if not title and soup.h1:
        title = clean(soup.h1.get_text())
    if not title:
        return None
    title = strip_site_suffix(title, meta("og:site_name"), url)

    author = ld_names(ld.get("author")) or ld_names(ld.get("creator"))
    if not author:
        author = meta("author", "book:author", "article:author")
        if author.lower().startswith("http"):
            author = ""
    if not author:
        tag = soup.select_one(
            '[itemprop="author"], [rel="author"], .author-name, '
            '.byline, .author'
        )
        if tag:
            author = re.sub(r"^\s*by\s+", "", clean(tag.get_text(" ")),
                            flags=re.IGNORECASE)[:80]
    author = author or "Unknown"

    genre = (ld_text(ld.get("genre")) or ld_text(ld.get("articleSection"))
             or meta("article:section", "book:genre"))
    if not genre:
        tag = soup.select_one(
            'a[rel~="category"], .cat-links a, .posted_in a'
        )
        if tag:
            genre = clean(tag.get_text())
    if not genre:
        genre = meta("keywords").split(",")[0].strip()

    date_text = (ld_text(ld.get("datePublished"))
                 or meta("book:release_date", "article:published_time"))
    year = ""
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", date_text)
    if m:
        year = m.group(1)

    offers = ld.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}
    price = offers.get("price") or offers.get("lowPrice") \
        or meta("product:price:amount", "og:price:amount")
    price = re.sub(r"[^\d.]", "", str(price or ""))

    rating_info = ld.get("aggregateRating")
    rating = ""
    if isinstance(rating_info, dict) and rating_info.get("ratingValue"):
        rating = clean(str(rating_info["ratingValue"]))

    availability = ld_text(offers.get("availability")).rsplit("/", 1)[-1]

    language = language_name(ld_text(ld.get("inLanguage"))) or \
        language_name(soup.html.get("lang") if soup.html else "")

    description = (ld_text(ld.get("description"))
                   or meta("og:description", "description"))
    description = clean(
        BeautifulSoup(html.unescape(description), PARSER).get_text(" ")
    )[:600]

    image = ld_text(ld.get("image")) or meta("og:image", "twitter:image")

    return new_book(
        title=title, author=author, genre=genre, language=language,
        release_year=year, price=price, rating=rating,
        availability=availability, description=description,
        cover_url=urljoin(url, image) if image else "", source_url=url
    )


OL_FIELDS = ("key,title,author_name,first_publish_year,subject,language,"
             "cover_i,ratings_average,edition_count")
OL_TOPICS = ["fiction", "history", "science", "fantasy", "romance",
             "mystery", "biography", "poetry", "philosophy", "art",
             "adventure", "children", "religion", "travel", "cooking"]
OL_LANGS = {
    "eng": "English", "fre": "French", "ger": "German", "spa": "Spanish",
    "ita": "Italian", "rus": "Russian", "chi": "Chinese", "jpn": "Japanese",
    "por": "Portuguese", "dut": "Dutch", "ara": "Arabic", "urd": "Urdu",
    "lat": "Latin", "gre": "Greek", "swe": "Swedish", "dan": "Danish",
    "nor": "Norwegian", "fin": "Finnish", "pol": "Polish", "heb": "Hebrew",
    "hin": "Hindi", "cze": "Czech", "hun": "Hungarian",
}


def ol_page_url(topic, page):
    return "https://openlibrary.org/search.json?" + urlencode({
        "q": topic, "page": page, "limit": 100, "fields": OL_FIELDS
    })


def parse_openlibrary(text):
    """Open Library JSON API page -> list of books."""
    data = json.loads(text)
    out = []
    for d in data.get("docs", []):
        title = clean(d.get("title", ""))
        key = d.get("key", "")
        if not title or not key:
            continue
        authors = d.get("author_name") or ["Unknown"]
        subjects = d.get("subject") or [""]
        langs = d.get("language") or []
        language = OL_LANGS.get(langs[0], "") if langs else ""
        cover = ""
        if d.get("cover_i"):
            cover = f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg"
        rating = ""
        if d.get("ratings_average"):
            rating = f"{float(d['ratings_average']):.2f}"
        editions = d.get("edition_count")
        out.append(new_book(
            title=title, author=", ".join(authors[:2]), genre=subjects[0],
            language=language, release_year=d.get("first_publish_year", ""),
            rating=rating,
            availability=f"{editions} editions" if editions else "",
            cover_url=cover, source_url="https://openlibrary.org" + key
        ))
    return out


def iter_openlibrary(topic=""):
    topics = [topic] if topic else OL_TOPICS
    for t in topics:
        text = fetch(ol_page_url(t, 1))
        if not text:
            continue
        try:
            found = int(json.loads(text).get("numFound", 0))
        except (ValueError, TypeError):
            continue
        pages = min(60, max(1, math.ceil(found / 100)))
        for p in range(1, pages + 1):
            yield ol_page_url(t, p)


def is_known_host(host):
    return any(h in host for h in
               ("gutenberg.org", "toscrape.com", "openlibrary.org"))


def parse_url(url):
    host = urlparse(url).netloc.lower()
    page = fetch(url, browser=not is_known_host(host))
    if not page:
        return None
    if "openlibrary.org" in host and "/search.json" in url:
        try:
            return parse_openlibrary(page)
        except ValueError:
            return None
    if "gutenberg.org" in host:
        return parse_gutenberg(page, url)
    if "toscrape.com" in host:
        return parse_toscrape(page, url)
    return parse_generic(page, url, strict=isinstance(url, CrawlUrl))


def iter_gutenberg(start):
    i = start
    while i <= GUTENBERG_MAX_ID:
        yield f"https://www.gutenberg.org/ebooks/{i}"
        i += 1


def iter_toscrape(start_url):
    page = start_url
    while page:
        text = fetch(page)
        if not text:
            return
        soup = BeautifulSoup(text, PARSER)
        for a in soup.select("article.product_pod h3 a[href]"):
            yield urljoin(page, a["href"])
        nxt = soup.select_one("li.next a[href]")
        page = urljoin(page, nxt["href"]) if nxt else None


def listing_links(soup, page_url):
    """Links on a listing page that probably lead to book/product pages."""
    host = site_of(page_url)
    found = {}

    def add(a):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            return
        link = urljoin(page_url, href).split("#")[0]
        p = urlparse(link)
        if p.scheme not in ("http", "https") or site_of(link) != host:
            return
        if p.path in ("", "/") or SKIP_PATH.search(p.path):
            return
        if norm_url(link) == norm_url(page_url):
            return
        found.setdefault(link, None)

    for selector in LISTING_SELECTORS:
        for a in soup.select(selector):
            add(a)
        if len(found) >= 3:
            break
    if len(found) < 3:
        for a in soup.select("a[href]"):
            add(a)
    return list(found)


def next_page_link(soup, page_url):
    for selector in NEXT_SELECTORS:
        tag = soup.select_one(selector)
        if tag and tag.get("href"):
            return urljoin(page_url, tag["href"]).split("#")[0]
    return None


def iter_generic(start_url):
    """Any website. A single book/article page is scraped directly. A
    home/category/listing page is crawled: every link that looks like a
    book page is yielded, and 'next page' links are followed."""
    text = fetch(start_url, browser=True)
    if not text:
        return
    soup = BeautifulSoup(text, PARSER)
    if page_is_detail(soup):
        yield start_url
        return

    links = listing_links(soup, start_url)
    if len(links) < 3 and not next_page_link(soup, start_url):
        yield start_url          # not a listing, treat it as one page
        return

    visited, sent, page_url = set(), set(), start_url
    while True:
        visited.add(norm_url(page_url))
        for link in links:
            key = norm_url(link)
            if key not in sent:
                sent.add(key)
                yield CrawlUrl(link)
        nxt = next_page_link(soup, page_url)
        if (not nxt or norm_url(nxt) in visited
                or len(visited) >= CRAWL_MAX_PAGES):
            return
        time.sleep(0.5)
        text = fetch(nxt, browser=True)
        if not text:
            return
        page_url, soup = nxt, BeautifulSoup(text, PARSER)
        links = listing_links(soup, nxt)


def iter_custom(url):
    host = urlparse(url).netloc.lower()
    is_product = re.search(r"/catalogue/.+_\d+/index\.html$", url)
    if "toscrape.com" in host:
        if is_product:
            yield url
        else:
            yield from iter_toscrape(url)
        return
    if "gutenberg.org" in host:
        yield url
        return
    yield from iter_generic(url)


class ScrapeWorker(QThread):
    batch = pyqtSignal(list)
    progress = pyqtSignal(int, int, int)
    finished_with = pyqtSignal(str)

    def __init__(self, factory, target, seen, threads=SCRAPE_THREADS,
                 delay=SCRAPE_DELAY, miss_limit=400, hint_url=""):
        super().__init__()
        self.factory = factory
        self.target = target
        self.seen = {norm_url(u) for u in seen}
        self.threads = threads
        self.delay = delay
        self.miss_limit = miss_limit
        self.hint_url = hint_url
        self._go = threading.Event()
        self._go.set()
        self._stop = False

    def pause(self):
        self._go.clear()

    def resume(self):
        self._go.set()

    def stop(self):
        self._stop = True
        self._go.set()

    def fetch_one(self, url):
        if self._stop:
            return None
        time.sleep(self.delay)
        try:
            return parse_url(url)
        except Exception:
            return None

    def empty_reason(self, collected, dupes):
        if collected:
            return "No more pages to scrape"
        if dupes:
            return "Already in books.csv, nothing new to add"
        why = FETCH_ERRORS.get(self.hint_url, "")
        return "No book could be read from that URL" + (
            f" ({why})" if why else ""
        )

    def run(self):
        """Sliding window: as soon as one request finishes, another starts,
        so one slow page never blocks the others."""
        collected, attempts, misses, dupes = 0, 0, 0, 0
        reason = "Finished"
        pending = set()
        try:
            urls = iter(self.factory())
            exhausted = False
            with ThreadPoolExecutor(self.threads) as pool:
                while not self._stop and collected < self.target:
                    self._go.wait()
                    if self._stop:
                        break

                    # keep the window full of in-flight requests
                    while not exhausted and len(pending) < self.threads * 3:
                        u = next(urls, None)
                        if u is None:
                            exhausted = True
                            break
                        if norm_url(u) in self.seen:
                            dupes += 1
                            continue
                        pending.add(pool.submit(self.fetch_one, u))

                    if not pending:
                        reason = self.empty_reason(collected, dupes)
                        break

                    done, pending = wait(
                        pending, timeout=1, return_when=FIRST_COMPLETED
                    )
                    good = []
                    for fut in done:
                        attempts += 1
                        try:
                            r = fut.result()
                        except Exception:
                            r = None
                        found = r if isinstance(r, list) else ([r] if r else [])
                        if not found:
                            misses += 1
                        for b in found:
                            key = norm_url(b["source_url"])
                            if key in self.seen:
                                dupes += 1
                                continue
                            if collected + len(good) >= self.target:
                                break
                            self.seen.add(key)
                            good.append(b)
                    if good:
                        collected += len(good)
                        misses = 0
                        self.batch.emit(good)
                    if done:
                        self.progress.emit(collected, self.target, attempts)
                    if misses >= self.miss_limit:
                        reason = "Stopped after many empty pages"
                        break

                for f in pending:
                    f.cancel()
            if self._stop:
                reason = "Stopped"
            elif collected >= self.target:
                reason = "Target reached"
        except Exception as error:
            reason = f"Error: {error}"
        self.finished_with.emit(reason)


class CoverManager(QObject):
    loaded = pyqtSignal(str)

    def __init__(self, cache_dir):
        super().__init__()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.pool = ThreadPoolExecutor(4)
        self.thumbs = {}
        self.pending = set()
        self.failed = set()

    def path_for(self, url):
        name = hashlib.md5(url.encode("utf-8")).hexdigest() + ".jpg"
        return self.cache_dir / name

    def request(self, url):
        if not url or url in self.pending or url in self.failed:
            return
        self.pending.add(url)
        self.pool.submit(self._download, url)

    def _download(self, url):
        path = self.path_for(url)
        try:
            if not path.exists():
                r = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
                r.raise_for_status()
                path.write_bytes(r.content)
            self.loaded.emit(url)
        except Exception:
            self.failed.add(url)
        finally:
            self.pending.discard(url)

    def thumb(self, url):
        if not url:
            return None
        if url in self.thumbs:
            return self.thumbs[url]
        path = self.path_for(url)
        if path.exists():
            pm = QPixmap(str(path))
            if pm.isNull():
                self.failed.add(url)
                return None
            pm = pm.scaled(42, 60, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
            self.thumbs[url] = pm
            return pm
        self.request(url)
        return None

    def pixmap(self, url, w, h):
        if not url:
            return None
        path = self.path_for(url)
        if path.exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                return pm.scaled(w, h, Qt.KeepAspectRatio,
                                 Qt.SmoothTransformation)
            return None
        self.request(url)
        return None


class BooksModel(QAbstractTableModel):
    COLS = ["Cover"] + HEADERS

    def __init__(self, covers):
        super().__init__()
        self.rows = []
        self.covers = covers

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def append(self, new_rows):
        if not new_rows:
            return
        first = len(self.rows)
        self.beginInsertRows(QModelIndex(), first, first + len(new_rows) - 1)
        self.rows.extend(new_rows)
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.COLS[section]
        return str(section + 1)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        book = self.rows[index.row()]
        col = index.column()
        if col == 0:
            if role == Qt.DecorationRole:
                return self.covers.thumb(book.get("cover_url", ""))
            return None
        value = book.get(FIELDS[col - 1], "")
        if role == Qt.DisplayRole:
            return value if len(value) <= 110 else value[:107] + "..."
        if role == Qt.ToolTipRole and len(value) > 110:
            return value[:600]
        return None


PALETTE = ["#6b4226", "#8b5a2b", "#4a2c1a", "#a0522d", "#7b3f00",
           "#5c3a21", "#c8905a", "#3e2214", "#9c6b3c", "#b5835a"]


class BackgroundWidget(QWidget):
    """Plain cocoa surface behind the whole window."""

    def __init__(self, cover_dir=None):
        super().__init__()

    def refresh(self):
        pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1c120d"))
        p.end()


class FuncWorker(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.result.emit(self.fn())
        except Exception as error:
            self.failed.emit(str(error))


def make_column_combo(none_text=None, all_text=None):
    box = QComboBox()
    if none_text:
        box.addItem(none_text, "")
    if all_text:
        box.addItem(all_text, "__all__")
    for field, header in zip(FIELDS, HEADERS):
        box.addItem(header, field)
    return box


def fill_ops(op_box, field):
    op_box.clear()
    op_box.addItems(NUM_OPS if field in NUMERIC else TEXT_OPS)


class MultiSortDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Multi-Level Sort")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.cols, self.orders = [], []
        for i in range(3):
            col = make_column_combo(none_text="(none)" if i else None)
            order = QComboBox()
            order.addItems(["Ascending", "Descending"])
            row = QHBoxLayout()
            row.addWidget(col, 3)
            row.addWidget(order, 1)
            form.addRow(f"Level {i + 1}:", row)
            self.cols.append(col)
            self.orders.append(order)
        self.algo = QComboBox()
        for name, info in ALGORITHMS.items():
            tag = "Stable" if info["stable"] else "Unstable"
            self.algo.addItem(f"{name} ({info['avg']}, {tag})", name)
        self.algo.setCurrentIndex(self.algo.findData("Merge"))
        form.addRow("Algorithm:", self.algo)
        layout.addLayout(form)
        layout.addWidget(QLabel(
            "Tip: Merge, Insertion, Bubble and Cocktail are stable."
        ))
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def levels(self):
        out, seen = [], set()
        for col, order in zip(self.cols, self.orders):
            field = col.currentData()
            if field and field not in seen:
                seen.add(field)
                out.append((field, order.currentIndex() == 1))
        return out


class FilterDialog(QDialog):
    ROWS = 5

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter (AND / OR / NOT)")
        self.resize(780, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Conditions are evaluated from top to bottom. Empty values are "
            "ignored. NOT flips that single condition."
        ))
        grid = QGridLayout()
        for c, name in enumerate(["Join", "", "Column", "Operator", "Value"]):
            grid.addWidget(QLabel(name), 0, c)
        self.rows = []
        for i in range(self.ROWS):
            if i == 0:
                join = QLabel("WHERE")
            else:
                join = QComboBox()
                join.addItems(["AND", "OR"])
            neg = QCheckBox("NOT")
            col = make_column_combo()
            op = QComboBox()
            fill_ops(op, FIELDS[0])
            val = QLineEdit()
            col.currentIndexChanged.connect(
                lambda _, c=col, o=op: fill_ops(o, c.currentData())
            )
            for c, widget in enumerate([join, neg, col, op, val]):
                grid.addWidget(widget, i + 1, c)
            self.rows.append((join, neg, col, op, val))
        grid.setColumnStretch(4, 1)
        layout.addLayout(grid)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Apply Filter")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def conditions(self):
        out = []
        for join, neg, col, op, val in self.rows:
            text = val.text().strip()
            if not text:
                continue
            j = "AND" if isinstance(join, QLabel) else join.currentText()
            out.append((j, neg.isChecked(), col.currentData(),
                        op.currentText(), text))
        return out


class BenchmarkDialog(QDialog):
    def __init__(self, parent, title, results):
        super().__init__(parent)
        self.setWindowTitle("Benchmark Results")
        self.resize(900, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        table = QTableWidget(len(results), 7)
        table.setHorizontalHeaderLabels([
            "Algorithm", "Time (ms)", "Comparisons", "Swaps / Moves",
            "Best | Avg | Worst", "Space", "Stable"
        ])
        fastest = min(r["ms"] for r in results)
        for row, r in enumerate(results):
            info = ALGORITHMS[r["name"]]
            cells = [
                r["name"], f"{r['ms']:,.2f}", f"{r['cmp']:,}",
                f"{r['swap']:,}",
                f"{info['best']} | {info['avg']} | {info['worst']}",
                info["space"], "Yes" if info["stable"] else "No"
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if r["ms"] == fastest:
                    item.setBackground(QColor("#d9a05b"))
                    item.setForeground(QColor("#2a1608"))
                else:
                    item.setBackground(QColor("#271a13"))
                    item.setForeground(QColor("#efe3d3"))
                table.setItem(row, col, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(table)
        layout.addWidget(QLabel("Fastest algorithm is highlighted."))


class MapDialog(QDialog):
    """Shows the folium map of the books inside the PyQt5 application."""

    def __init__(self, parent, map_file, note):
        super().__init__(parent)
        self.map_file = Path(map_file)
        self.setWindowTitle("Books Map")
        self.resize(1150, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        info = QLabel(note)
        info.setObjectName("muted")
        info.setWordWrap(True)
        btn_browser = QPushButton("Open in browser")
        btn_browser.clicked.connect(
            lambda: webbrowser.open(self.map_file.as_uri())
        )
        top.addWidget(info, 1)
        top.addWidget(btn_browser)
        layout.addLayout(top)

        self.web = QWebEngineView()
        # the map page is a local file but loads its tiles from the internet
        self.web.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )
        self.web.setUrl(QUrl.fromLocalFile(str(self.map_file)))
        layout.addWidget(self.web, 1)


def dark_palette():
    pal = QPalette()
    cream = QColor("#efe3d3")
    pal.setColor(QPalette.Window, QColor("#1c120d"))
    pal.setColor(QPalette.WindowText, cream)
    pal.setColor(QPalette.Base, QColor("#160e0a"))
    pal.setColor(QPalette.AlternateBase, QColor("#251811"))
    pal.setColor(QPalette.Text, cream)
    pal.setColor(QPalette.Button, QColor("#33231a"))
    pal.setColor(QPalette.ButtonText, cream)
    pal.setColor(QPalette.Highlight, QColor("#d9a05b"))
    pal.setColor(QPalette.HighlightedText, QColor("#2a1608"))
    pal.setColor(QPalette.ToolTipBase, QColor("#33231a"))
    pal.setColor(QPalette.ToolTipText, cream)
    if hasattr(QPalette, "PlaceholderText"):
        pal.setColor(QPalette.PlaceholderText, QColor("#7d6b5a"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#6f5f50"))
    return pal


STYLE = """
QWidget { color:#efe3d3; font-family:'Segoe UI','Arial'; font-size:10pt; }
QMainWindow, QDialog { background:#1c120d; }
QLabel { background:transparent; }
QLabel#muted { color:#a89580; }
QLabel#status { color:#a89580; padding:2px 6px; }

QFrame#panel { background:#271a13; border:1px solid #45311f;
    border-radius:10px; }

QTabWidget::pane { background:#271a13; border:1px solid #45311f;
    border-radius:10px; top:-1px; }
QTabBar::tab { background:transparent; color:#a89580; padding:9px 22px;
    margin-right:2px; border:none; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#efe3d3; border-bottom:2px solid #d9a05b; }
QTabBar::tab:hover:!selected { color:#efe3d3; }

QLineEdit, QTextEdit, QComboBox, QSpinBox { background:#160e0a;
    color:#efe3d3; border:1px solid #45311f; border-radius:6px;
    padding:5px 8px; selection-background-color:#d9a05b;
    selection-color:#2a1608; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border:1px solid #d9a05b; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background:#1c120d; color:#6f5f50; }
QComboBox QAbstractItemView { background:#271a13; color:#efe3d3;
    border:1px solid #45311f; selection-background-color:#5c3e27;
    selection-color:#ffffff; outline:0; }

QPushButton { background:#33231a; color:#efe3d3; border:1px solid #4a3626;
    border-radius:6px; padding:6px 14px; }
QPushButton:hover { background:#41301f; border-color:#6a4d35; }
QPushButton:pressed { background:#271a13; }
QPushButton:disabled { background:#21160f; color:#6f5f50;
    border-color:#2f2217; }
QPushButton#primary { background:#d9a05b; color:#2a1608;
    border:1px solid #d9a05b; font-weight:600; }
QPushButton#primary:hover { background:#e6b374; border-color:#e6b374; }
QPushButton#primary:pressed { background:#c48d4a; }
QPushButton#primary:disabled { background:#463829; color:#8a7a68;
    border-color:#463829; }
QPushButton#danger { background:transparent; color:#e08a74;
    border:1px solid #6b3a2e; }
QPushButton#danger:hover { background:#3a1f19; border-color:#8a4a3a; }
QPushButton#danger:disabled { background:transparent; color:#6f5f50;
    border-color:#3a2a22; }
QPushButton#algo { padding:6px 4px; font-size:9pt; }

QTableView, QTableWidget { background:#1f140e;
    alternate-background-color:#251811; color:#efe3d3;
    gridline-color:#33231a; selection-background-color:#5c3e27;
    selection-color:#ffffff; border:1px solid #45311f;
    border-radius:10px; }
QTableView::item { padding:4px 8px; }
QHeaderView::section { background:#271a13; color:#d9a05b; padding:8px 8px;
    border:none; border-bottom:1px solid #45311f;
    border-right:1px solid #33231a; }
QTableCornerButton::section { background:#271a13; border:none; }

QProgressBar { border:1px solid #45311f; border-radius:6px;
    text-align:center; background:#160e0a; color:#ffffff;
    min-height:18px; }
QProgressBar::chunk { background:#b07a3f; border-radius:5px; }

QScrollArea { background:transparent; border:none; }
QScrollBar:vertical { background:transparent; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#4a3626; border-radius:5px;
    min-height:30px; }
QScrollBar::handle:vertical:hover { background:#6a4d35; }
QScrollBar:horizontal { background:transparent; height:10px; margin:0; }
QScrollBar::handle:horizontal { background:#4a3626; border-radius:5px;
    min-width:30px; }
QScrollBar::handle:horizontal:hover { background:#6a4d35; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:none; }

QToolTip { background:#33231a; color:#efe3d3; border:1px solid #6a4d35;
    padding:4px 6px; }
"""


class BooksApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chocolate Books Console")
        self.resize(1500, 900)
        self.setMinimumSize(1100, 700)

        self.books = load_books()
        self.view = list(self.books)
        self.filter_active = False
        self.selected = None
        self.inputs = {}
        self.scraper = None
        self.scrape_paused = False
        self.tasks = set()
        self.unsaved = 0
        self.save_failed = False
        self.lockables = []
        self.busy_locked = []

        self.covers = CoverManager(COVER_DIR)
        self.model = BooksModel(self.covers)
        self.model.set_rows(self.view)

        self.bg = BackgroundWidget(COVER_DIR)
        self.setCentralWidget(self.bg)
        root = QVBoxLayout(self.bg)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(10)

        root.addWidget(self.build_tools())
        root.addLayout(self.build_body(), 1)
        root.addWidget(self.build_actions())

        self.status = QLabel()
        self.status.setObjectName("status")
        root.addWidget(self.status)

        self.cover_timer = QTimer(self)
        self.cover_timer.setSingleShot(True)
        self.cover_timer.setInterval(500)
        self.cover_timer.timeout.connect(self.on_covers_refresh)
        self.covers.loaded.connect(self.on_cover_loaded)

        self.quick_timer = QTimer(self)
        self.quick_timer.setSingleShot(True)
        self.quick_timer.setInterval(250)
        self.quick_timer.timeout.connect(self.do_quick_search)

        self.update_status()

    #  UI builders
    def build_tools(self):
        tabs = QTabWidget()
        tabs.addTab(self.build_scraper_box(), "Collect data")
        tabs.addTab(self.build_search_box(), "Search and filter")
        tabs.addTab(self.build_sort_box(), "Sort and benchmark")

        def fit(index):
            # size the tab area to the visible page, not the tallest one
            page = tabs.widget(index)
            tabs.setFixedHeight(
                tabs.tabBar().sizeHint().height()
                + page.sizeHint().height() + 8
            )

        tabs.currentChanged.connect(fit)
        fit(0)
        return tabs

    def build_scraper_box(self):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(12)

        self.source_combo = QComboBox()
        self.source_combo.addItems([
            "Project Gutenberg (book pages)",
            "Books to Scrape (book pages)",
            "Custom URL (bonus)",
            "Open Library (JSON API)"
        ])
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "Paste a URL: a Gutenberg book page, a books.toscrape.com "
            "page or category, or any book page"
        )
        self.url_edit.setEnabled(False)

        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 100000)
        self.target_spin.setValue(15000)
        self.target_spin.setSingleStep(500)

        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_resume = QPushButton("Resume")
        self.btn_stop = QPushButton("Stop")
        self.btn_start.clicked.connect(self.start_scrape)
        self.btn_pause.clicked.connect(self.pause_scrape)
        self.btn_resume.clicked.connect(self.resume_scrape)
        self.btn_stop.clicked.connect(self.stop_scrape)
        self.set_scrape_buttons("idle")

        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m books")
        self.progress.setValue(0)
        self.scrape_label = QLabel("Idle")

        self.btn_start.setObjectName("primary")
        self.btn_stop.setObjectName("danger")
        self.scrape_label.setObjectName("muted")
        self.scrape_label.setWordWrap(True)
        self.source_combo.setMinimumWidth(230)

        grid.addWidget(QLabel("Source"), 0, 0)
        grid.addWidget(self.source_combo, 0, 1)
        grid.addWidget(QLabel("URL"), 0, 2)
        grid.addWidget(self.url_edit, 0, 3)
        grid.addWidget(QLabel("Target books"), 0, 4)
        grid.addWidget(self.target_spin, 0, 5)
        for i, b in enumerate([self.btn_start, self.btn_pause,
                               self.btn_resume, self.btn_stop]):
            grid.addWidget(b, 0, 6 + i)
        grid.addWidget(self.progress, 1, 0, 1, 6)
        grid.addWidget(self.scrape_label, 1, 6, 1, 4)
        grid.setColumnStretch(3, 1)
        grid.setRowStretch(2, 1)
        return box

    def build_search_box(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(12)

        self.quick_edit = QLineEdit()
        self.quick_edit.setPlaceholderText("Quick search across all columns...")
        self.quick_edit.textChanged.connect(
            lambda: self.quick_timer.start()
        )

        self.s_col = make_column_combo(all_text="All columns")
        self.s_col.setCurrentIndex(self.s_col.findData("title"))
        self.s_op = QComboBox()
        fill_ops(self.s_op, "title")
        self.s_col.currentIndexChanged.connect(self.on_search_col_changed)
        self.s_value = QLineEdit()
        self.s_value.setPlaceholderText("Value")
        self.s_value.returnPressed.connect(self.run_column_search)
        self.s_algo = QComboBox()
        self.s_algo.addItems(list(SEARCH_ALGOS))
        self.s_algo.currentTextChanged.connect(self.on_search_algo_changed)
        self.s_scope = QComboBox()
        self.s_scope.addItems(["Search full dataset", "Search current results"])

        btn_search = QPushButton("Search")
        btn_search.clicked.connect(self.run_column_search)
        btn_filter = QPushButton("Advanced AND / OR / NOT...")
        btn_filter.clicked.connect(self.open_filter_dialog)
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self.reset_filters)

        btn_search.setObjectName("primary")

        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)
        quick_row.addWidget(QLabel("Quick search"))
        quick_row.addWidget(self.quick_edit, 1)
        quick_row.addWidget(btn_reset)
        v.addLayout(quick_row)

        col_row = QHBoxLayout()
        col_row.setSpacing(10)
        col_row.addWidget(QLabel("Column"))
        col_row.addWidget(self.s_col, 1)
        col_row.addWidget(self.s_op)
        col_row.addWidget(self.s_value, 2)
        col_row.addWidget(QLabel("Algorithm"))
        col_row.addWidget(self.s_algo)
        col_row.addWidget(self.s_scope)
        col_row.addWidget(btn_search)
        col_row.addWidget(btn_filter)
        v.addLayout(col_row)

        self.search_info = QLabel(SEARCH_ALGOS["Linear Search"])
        self.search_info.setObjectName("muted")
        self.search_info.setWordWrap(True)
        v.addWidget(self.search_info)
        v.addStretch(1)
        self.lockables.append(box)
        return box

    def build_sort_box(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.sort_col = make_column_combo()
        self.sort_order = QComboBox()
        self.sort_order.addItems(["Ascending", "Descending"])
        self.sort_scope = QComboBox()
        self.sort_scope.addItems(["Full dataset", "Filtered results only"])
        self.bench_rows = QSpinBox()
        self.bench_rows.setRange(100, 100000)
        self.bench_rows.setValue(3000)
        self.bench_rows.setSingleStep(500)
        self.bench_rows.setToolTip(
            "Maximum rows used by Benchmark (slow algorithms are O(n^2))"
        )
        top.addWidget(QLabel("Column"))
        top.addWidget(self.sort_col, 1)
        top.addWidget(QLabel("Order"))
        top.addWidget(self.sort_order)
        top.addWidget(QLabel("Scope"))
        top.addWidget(self.sort_scope)
        top.addWidget(QLabel("Benchmark rows"))
        top.addWidget(self.bench_rows)
        v.addLayout(top)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(8)
        sort_buttons = []
        for name in ALGORITHMS:
            info = ALGORITHMS[name]
            tag = "Stable" if info["stable"] else "Unstable"
            btn = QPushButton(f"{name} Sort\n{info['avg']} | {tag}")
            btn.setObjectName("algo")
            btn.setMinimumHeight(46)
            btn.setToolTip(complexity_text(name))
            btn.clicked.connect(lambda _, n=name: self.sort_single(n))
            sort_buttons.append(btn)
        btn_multi = QPushButton("Multi-Level Sort...")
        btn_multi.setObjectName("algo")
        btn_multi.setMinimumHeight(46)
        btn_multi.clicked.connect(self.sort_multi)
        btn_bench = QPushButton("Benchmark All")
        btn_bench.setObjectName("primary")
        btn_bench.setMinimumHeight(46)
        btn_bench.clicked.connect(self.run_benchmark_clicked)
        sort_buttons += [btn_multi, btn_bench]
        self.busy_locked.extend(sort_buttons)
        for i, btn in enumerate(sort_buttons):
            buttons.addWidget(btn, i // 5, i % 5)
        for c in range(5):
            buttons.setColumnStretch(c, 1)
        v.addLayout(buttons)

        self.sort_info = QLabel(
            "Pick a column and press a sorting button. Labels show average "
            "time complexity and stability. Hover for best, worst and space."
        )
        self.sort_info.setObjectName("muted")
        self.sort_info.setWordWrap(True)
        v.addWidget(self.sort_info)
        v.addStretch(1)
        self.lockables.append(box)
        return box

    def build_body(self):
        body = QHBoxLayout()
        body.setSpacing(12)

        left = QFrame()
        left.setObjectName("panel")
        left.setFixedWidth(400)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(14, 14, 14, 14)
        lv.setSpacing(12)

        self.cover_label = QLabel("Select a book to see its cover")
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedHeight(170)
        self.cover_label.setWordWrap(True)
        self.cover_label.setStyleSheet(
            "background:#160e0a; border:1px solid #45311f;"
            "border-radius:8px; color:#a89580;"
        )
        lv.addWidget(self.cover_label)

        form_widget = QWidget()
        form_widget.setObjectName("formHost")
        form = QFormLayout(form_widget)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 8, 0)
        for field, header in zip(FIELDS, HEADERS):
            if field == "description":
                widget = QTextEdit()
                widget.setFixedHeight(80)
            else:
                widget = QLineEdit()
            self.inputs[field] = widget
            form.addRow(header, widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        scroll.viewport().setAutoFillBackground(False)
        form_widget.setAutoFillBackground(False)
        form_widget.setStyleSheet(
            "QWidget#formHost { background: transparent; }"
            "QLabel { color:#a89580; }"
        )
        lv.addWidget(scroll, 1)

        record = QGridLayout()
        record.setSpacing(8)
        btn_add = QPushButton("Add book")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.add_book)
        btn_update = QPushButton("Update book")
        btn_update.clicked.connect(self.update_book)
        btn_delete = QPushButton("Delete book")
        btn_delete.setObjectName("danger")
        btn_delete.clicked.connect(self.delete_book)
        btn_clear = QPushButton("Clear form")
        btn_clear.clicked.connect(self.clear_form)
        record.addWidget(btn_add, 0, 0)
        record.addWidget(btn_update, 0, 1)
        record.addWidget(btn_delete, 1, 0)
        record.addWidget(btn_clear, 1, 1)
        lv.addLayout(record)
        self.busy_locked.extend([btn_add, btn_update, btn_delete])
        self.lockables.append(left)
        body.addWidget(left)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setIconSize(QSize(42, 60))
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.verticalHeader().setDefaultSectionSize(64)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.horizontalHeader().sectionClicked.connect(
            self.on_header_clicked
        )
        for i, field in enumerate(FIELDS):
            self.table.setColumnWidth(i + 1, COLUMN_WIDTHS[field])
        self.table.selectionModel().currentRowChanged.connect(
            self.on_row_changed
        )
        self.lockables.append(self.table)
        body.addWidget(self.table, 1)
        return body

    def on_header_clicked(self, section):
        if section == 0:
            return
        index = self.sort_col.findData(FIELDS[section - 1])
        if index < 0:
            return
        if self.sort_col.currentIndex() == index:
            self.sort_order.setCurrentIndex(1 - self.sort_order.currentIndex())
        self.sort_col.setCurrentIndex(index)
        self.sort_info.setText(
            f"Column: {HEADERS[section - 1]} | "
            f"{self.sort_order.currentText()}. "
            "Press a sorting button to choose the algorithm."
        )

    def build_actions(self):
        box = QFrame()
        box.setObjectName("panel")
        row = QHBoxLayout(box)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        actions = [
            ("Import CSV", self.import_csv),
            ("Export CSV", self.export_csv),
            ("Open map", self.open_map),
            ("Open source page", self.open_source),
        ]
        for label, fn in actions:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            row.addWidget(btn)
            if label == "Import CSV":
                self.busy_locked.append(btn)
        row.addStretch(1)
        btn_shown = QPushButton("Delete all shown")
        btn_shown.setObjectName("danger")
        btn_shown.clicked.connect(self.delete_shown)
        row.addWidget(btn_shown)
        self.busy_locked.append(btn_shown)
        self.lockables.append(box)
        return box

    def update_status(self):
        text = (
            f"Showing {len(self.view):,} of {len(self.books):,} books"
            f"  |  File: {CSV_FILE.name}"
        )
        if self.save_failed:
            text += "  |  NOT SAVED: close books.csv if it is open in Excel"
        self.status.setText(text)
        self.status.setStyleSheet("color:#e08a74;" if self.save_failed else "")

    def set_view(self, rows, filtered):
        self.view = rows
        self.filter_active = filtered
        self.model.set_rows(self.view)
        self.update_status()

    def persist(self, quiet=False):
        try:
            save_books(self.books)
            self.unsaved = 0
            if self.save_failed:
                self.save_failed = False
                self.update_status()
            return True
        except OSError as error:
            self.save_failed = True
            self.update_status()
            if not quiet:
                QMessageBox.critical(self, "Save Error", str(error))
            return False

    def index_of(self, book, rows):
        for i, b in enumerate(rows):
            if b is book:
                return i
        return -1

    def scraper_running(self):
        return (self.scraper is not None and self.scraper.isRunning()
                and not self.scrape_paused)

    def set_busy(self, busy):
        # Lock only what could clash with a running sort: other sorts and
        # anything that edits or deletes books. Searching, browsing, tabs
        # and exporting stay usable.
        for widget in self.busy_locked:
            widget.setEnabled(not busy)

    def run_task(self, fn, on_ok, busy_text):
        self.set_busy(True)
        self.sort_info.setText(busy_text)
        self.status.setText(
            f"{busy_text} Searching and browsing still work."
        )
        worker = FuncWorker(fn)
        self.tasks.add(worker)

        def done(result):
            self.tasks.discard(worker)
            self.set_busy(False)
            self.update_status()
            on_ok(result)

        def failed(message):
            self.tasks.discard(worker)
            self.set_busy(False)
            self.update_status()
            QMessageBox.critical(self, "Task Failed", message)

        worker.result.connect(done)
        worker.failed.connect(failed)
        worker.start()

    def on_cover_loaded(self, url):
        if not self.cover_timer.isActive():
            self.cover_timer.start()
        if self.selected and self.selected.get("cover_url") == url:
            self.show_cover(self.selected)

    def on_covers_refresh(self):
        self.table.viewport().update()
        self.bg.refresh()

    def show_cover(self, book):
        url = book.get("cover_url", "")
        pm = self.covers.pixmap(url, 200, 230)
        if pm is not None:
            self.cover_label.setPixmap(pm)
        else:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText(
                "Loading cover..." if url else "No cover available"
            )

    def input_value(self, field):
        widget = self.inputs[field]
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return widget.text().strip()

    def set_input_value(self, field, value):
        widget = self.inputs[field]
        if isinstance(widget, QTextEdit):
            widget.setPlainText(value or "")
        else:
            widget.setText(value or "")

    def on_row_changed(self, current, previous):
        row = current.row()
        if row < 0 or row >= len(self.view):
            return
        self.selected = self.view[row]
        for field in FIELDS:
            self.set_input_value(field, self.selected.get(field, ""))
        self.show_cover(self.selected)

    def read_form(self):
        book = {f: self.input_value(f) for f in FIELDS}
        if not book["title"]:
            QMessageBox.warning(self, "Missing Information",
                                "Book title is required.")
            return None
        for field in ("release_year", "downloads", "price", "rating"):
            if book[field]:
                try:
                    float(book[field])
                except ValueError:
                    QMessageBox.warning(self, "Invalid Number",
                                        f"{field} must be a number.")
                    return None
        for field, limit in (("latitude", 90), ("longitude", 180)):
            if book[field]:
                try:
                    number = float(book[field])
                except ValueError:
                    QMessageBox.warning(self, "Invalid Coordinate",
                                        f"{field} must be a number.")
                    return None
                if not -limit <= number <= limit:
                    QMessageBox.warning(
                        self, "Invalid Coordinate",
                        f"{field} must be between {-limit} and {limit}."
                    )
                    return None
        return new_book(**book)

    def add_book(self):
        book = self.read_form()
        if book is None:
            return
        self.books.append(book)
        self.set_view(list(self.books), False)
        self.persist()
        self.clear_form()

    def update_book(self):
        if self.selected is None:
            QMessageBox.information(self, "Select a Book",
                                    "Select a book from the table first.")
            return
        book = self.read_form()
        if book is None:
            return
        i = self.index_of(self.selected, self.books)
        j = self.index_of(self.selected, self.view)
        if i >= 0:
            self.books[i] = book
        if j >= 0:
            self.view[j] = book
        self.selected = None
        self.set_view(self.view, self.filter_active)
        self.persist()
        self.clear_form()

    def delete_book(self):
        if self.selected is None:
            QMessageBox.information(self, "Select a Book",
                                    "Select a book from the table first.")
            return
        answer = QMessageBox.question(
            self, "Confirm Delete", "Delete the selected book?",
            QMessageBox.Yes | QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        i = self.index_of(self.selected, self.books)
        j = self.index_of(self.selected, self.view)
        if i >= 0:
            del self.books[i]
        if j >= 0:
            del self.view[j]
        self.selected = None
        self.set_view(self.view, self.filter_active)
        self.persist()
        self.clear_form()

    def delete_shown(self):
        count = len(self.view)
        if count == 0:
            QMessageBox.information(self, "Delete", "Nothing is shown.")
            return
        if self.scraper_running():
            QMessageBox.information(
                self, "Scraping in progress",
                "Pause or stop the scraper first."
            )
            return
        everything = count == len(self.books)
        text = (f"Delete ALL {count:,} books?" if everything
                else f"Delete the {count:,} books currently shown?")
        answer = QMessageBox.question(
            self, "Confirm Delete", text + "\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        gone = {id(b) for b in self.view}
        self.books[:] = [b for b in self.books if id(b) not in gone]
        self.selected = None
        self.set_view(list(self.books), False)
        self.persist()
        self.clear_form()

    def clear_form(self):
        self.selected = None
        for widget in self.inputs.values():
            widget.clear()
        self.table.clearSelection()
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("Select a book to see its cover")

    def on_search_col_changed(self):
        field = self.s_col.currentData()
        if field == "__all__":
            self.s_op.clear()
            self.s_op.addItem("contains")
        else:
            fill_ops(self.s_op, field)

    def on_search_algo_changed(self, name):
        self.search_info.setText(SEARCH_ALGOS[name])

    def do_quick_search(self):
        query = self.quick_edit.text().strip().casefold()
        if not query:
            self.set_view(list(self.books), False)
            return
        rows = [
            b for b in self.books
            if any(query in str(b.get(f, "")).casefold() for f in FIELDS)
        ]
        self.set_view(rows, True)

    def run_column_search(self):
        value = self.s_value.text().strip()
        if not value:
            QMessageBox.information(self, "Search", "Enter a value first.")
            return
        field = self.s_col.currentData()
        op = self.s_op.currentText()
        algo = self.s_algo.currentText()
        pool = (self.books if self.s_scope.currentIndex() == 0
                else list(self.view))
        start = time.perf_counter()
        if field == "__all__":
            q = value.casefold()
            rows = [
                b for b in pool
                if any(q in str(b.get(f, "")).casefold() for f in FIELDS)
            ]
            comps, prep, used = len(pool), 0.0, "Linear Search (all columns)"
        else:
            rows, comps, prep, used = search_column(
                pool, field, op, value, algo
            )
        total = (time.perf_counter() - start) * 1000
        self.quick_edit.blockSignals(True)
        self.quick_edit.clear()
        self.quick_edit.blockSignals(False)
        self.set_view(rows, True)
        self.search_info.setText(
            f"{used} | {len(rows):,} matches | search {total - prep:,.3f} ms"
            + (f" (+ {prep:,.2f} ms to sort first)" if prep else "")
            + f" | comparisons {comps:,}"
        )

    def open_filter_dialog(self):
        dialog = FilterDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        conditions = dialog.conditions()
        if not conditions:
            QMessageBox.information(self, "Filter", "Add at least one value.")
            return
        start = time.perf_counter()
        rows = [b for b in self.books if evaluate_conditions(b, conditions)]
        ms = (time.perf_counter() - start) * 1000
        self.quick_edit.blockSignals(True)
        self.quick_edit.clear()
        self.quick_edit.blockSignals(False)
        self.set_view(rows, True)
        self.search_info.setText(
            f"Composite filter ({len(conditions)} conditions) | "
            f"{len(rows):,} matches | {ms:,.2f} ms"
        )

    def reset_filters(self):
        self.quick_edit.blockSignals(True)
        self.quick_edit.clear()
        self.quick_edit.blockSignals(False)
        self.s_value.clear()
        self.set_view(list(self.books), False)
        self.search_info.setText(SEARCH_ALGOS[self.s_algo.currentText()])

    def sort_pool(self):
        if self.sort_scope.currentIndex() == 0:
            return self.books, "full"
        return self.view, "view"

    def sort_blocked(self):
        if self.scraper_running():
            QMessageBox.information(
                self, "Scraping in progress",
                "Pause or stop the scraper before sorting."
            )
            return True
        return False

    def sort_single(self, algo):
        field = self.sort_col.currentData()
        desc = self.sort_order.currentIndex() == 1
        self.start_sort(algo, [(field, desc)])

    def sort_multi(self):
        dialog = MultiSortDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        levels = dialog.levels()
        if levels:
            self.start_sort(dialog.algo.currentData(), levels)

    def start_sort(self, algo, levels):
        if self.sort_blocked():
            return
        pool, scope = self.sort_pool()
        if not pool:
            QMessageBox.information(self, "Sort", "There are no books to sort.")
            return
        if algo in QUADRATIC and len(pool) > 8000:
            answer = QMessageBox.question(
                self, "Slow algorithm",
                f"{algo} sort is O(n^2) and {len(pool):,} rows may take "
                "several minutes. Continue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return
        rows = list(pool)
        view_ref = self.view
        names = ", ".join(
            HEADERS[FIELDS.index(f)] + (" (desc)" if d else "")
            for f, d in levels
        )

        def done(result):
            sorted_rows, ms, comps, swaps = result
            if scope == "full":
                known = {id(r) for r in sorted_rows}
                extra = [b for b in self.books if id(b) not in known]
                self.books[:] = sorted_rows + extra
                if self.filter_active:
                    ids = {id(b) for b in self.view}
                    view = [b for b in self.books if id(b) in ids]
                else:
                    view = list(self.books)
                self.set_view(view, self.filter_active)
            elif self.view is view_ref:
                self.set_view(sorted_rows, self.filter_active)
            else:
                self.sort_info.setText(
                    "The results changed while sorting, so the sorted view "
                    "was not applied. Press the sort button again."
                )
                return
            self.persist()
            self.sort_info.setText(
                f"{algo} Sort | by {names} | {len(sorted_rows):,} rows | "
                f"{ms:,.2f} ms | comparisons {comps:,} | "
                f"swaps/moves {swaps:,} | {complexity_text(algo)}"
            )

        self.run_task(lambda: run_sort(rows, levels, algo), done,
                      f"Sorting with {algo}...")

    def run_benchmark_clicked(self):
        if self.sort_blocked():
            return
        pool, _ = self.sort_pool()
        if not pool:
            QMessageBox.information(self, "Benchmark", "No books to sort.")
            return
        field = self.sort_col.currentData()
        desc = self.sort_order.currentIndex() == 1
        rows = list(pool)[: self.bench_rows.value()]
        title = (
            f"Column: {HEADERS[FIELDS.index(field)]} | "
            f"{'Descending' if desc else 'Ascending'} | "
            f"{len(rows):,} of {len(pool):,} rows used"
        )

        def done(results):
            self.sort_info.setText("Benchmark finished.")
            BenchmarkDialog(self, title, results).exec_()

        self.run_task(lambda: run_benchmark(rows, [(field, desc)]), done,
                      "Benchmarking all algorithms...")

    def set_scrape_buttons(self, state):
        self.btn_start.setEnabled(state == "idle")
        self.btn_pause.setEnabled(state == "running")
        self.btn_resume.setEnabled(state == "paused")
        self.btn_stop.setEnabled(state in ("running", "paused"))

    def on_source_changed(self, index):
        self.url_edit.setEnabled(index in (2, 3))
        if index == 3:
            self.url_edit.setPlaceholderText(
                "Topic to search, e.g. fantasy (leave empty to cover "
                "15 popular topics)"
            )
        else:
            self.url_edit.setPlaceholderText(
                "Paste a URL: a Gutenberg book page, a books.toscrape.com "
                "page or category, or any website with book pages"
            )
        if index == 1:
            self.target_spin.setValue(1000)
        elif index in (0, 3):
            self.target_spin.setValue(15000)
        elif index == 2:
            self.target_spin.setValue(50)

    def start_scrape(self):
        if self.scraper is not None and self.scraper.isRunning():
            return
        source = self.source_combo.currentIndex()
        options = {}
        seen = {b["source_url"] for b in self.books if b.get("source_url")}
        if source == 0:
            ids = []
            for url in seen:
                m = re.search(r"gutenberg\.org/ebooks/(\d+)$", url)
                if m:
                    ids.append(int(m.group(1)))
            start = max(ids) + 1 if ids else 1
            factory = lambda: iter_gutenberg(start)
        elif source == 1:
            factory = lambda: iter_toscrape(
                "https://books.toscrape.com/catalogue/page-1.html"
            )
        elif source == 3:
            topic = self.url_edit.text().strip()
            factory = lambda: iter_openlibrary(topic)
            options = dict(threads=1, delay=0.7, miss_limit=24)
        else:
            url = self.url_edit.text().strip()
            if not url.lower().startswith(("http://", "https://")):
                QMessageBox.warning(self, "URL needed",
                                    "Enter a full URL starting with http.")
                return
            if re.search(r"\.(jpe?g|png|gif|webp|svg|pdf|css|js|zip)$",
                         urlparse(url).path, re.IGNORECASE):
                QMessageBox.warning(
                    self, "Not a web page",
                    "That link is an image or file, not a book page.\n\n"
                    "Paste a page link instead, for example:\n"
                    "https://books.toscrape.com/catalogue/"
                    "a-light-in-the-attic_1000/index.html\n"
                    "or a whole category:\n"
                    "https://books.toscrape.com/catalogue/category/books/"
                    "travel_2/index.html\n"
                    "(for a category set Target books to 50 or more)"
                )
                return
            factory = lambda: iter_custom(url)
            # polite crawl for unknown websites + remember the URL so the
            # real reason (blocked, 404...) can be shown if nothing is read
            options = dict(threads=4, delay=0.4, miss_limit=60, hint_url=url)

        target = self.target_spin.value()
        self.scraper = ScrapeWorker(factory, target, seen, **options)
        self.scraper.batch.connect(self.on_scrape_batch)
        self.scraper.progress.connect(self.on_scrape_progress)
        self.scraper.finished_with.connect(self.on_scrape_done)
        self.scrape_paused = False
        self.progress.setMaximum(target)
        self.progress.setValue(0)
        self.scrape_label.setText("Scraping...")
        self.set_scrape_buttons("running")
        self.scraper.start()

    def pause_scrape(self):
        if self.scraper:
            self.scraper.pause()
            self.scrape_paused = True
            self.set_scrape_buttons("paused")
            self.scrape_label.setText("Paused")

    def resume_scrape(self):
        if self.scraper:
            self.scraper.resume()
            self.scrape_paused = False
            self.set_scrape_buttons("running")
            self.scrape_label.setText("Scraping...")

    def stop_scrape(self):
        if self.scraper:
            self.scraper.stop()
            self.scrape_label.setText("Stopping...")

    def on_scrape_batch(self, new_books):
        self.books.extend(new_books)
        if not self.filter_active:
            self.model.append(new_books)
        self.unsaved += len(new_books)
        if self.unsaved >= SAVE_EVERY:
            self.persist(quiet=True)
        self.update_status()

    def on_scrape_progress(self, done, target, attempts):
        self.progress.setMaximum(target)
        self.progress.setValue(done)
        if self.scrape_paused:
            return
        self.scrape_label.setText(
            f"Scraped {done:,} of {target:,} | pages tried {attempts:,}"
        )

    def on_scrape_done(self, reason):
        self.scrape_paused = False
        self.set_scrape_buttons("idle")
        saved = self.persist(quiet=True)
        note = f"Saved to {CSV_FILE.name}" if saved else "NOT saved (close books.csv in Excel)"
        self.scrape_label.setText(f"{reason}. {note}")
        self.update_status()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Books", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            imported = read_csv_file(path)
        except (OSError, csv.Error) as error:
            QMessageBox.critical(self, "Import Failed", str(error))
            return
        seen = {b["source_url"] for b in self.books if b.get("source_url")}
        added = []
        for row in imported:
            url = row.get("source_url", "")
            if url and url in seen:
                continue
            if url:
                seen.add(url)
            added.append(new_book(**row))
        self.books.extend(added)
        self.set_view(list(self.books), False)
        self.persist()
        QMessageBox.information(
            self, "Import Complete",
            f"Read {len(imported):,} rows and added {len(added):,} new books."
        )

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Books", "books_export.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            write_csv_file(path, self.view)
        except OSError as error:
            QMessageBox.critical(self, "Export Failed", str(error))
            return
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(self.view):,} books (current view)."
        )

    def open_source(self):
        if self.selected is None or not self.selected.get("source_url"):
            QMessageBox.information(self, "Source Page",
                                    "Select a book that has a source URL.")
            return
        webbrowser.open(self.selected["source_url"])

    def open_map(self):
        mapped = []
        for book in self.view:
            try:
                lat = float(book.get("latitude", ""))
                lon = float(book.get("longitude", ""))
            except (TypeError, ValueError):
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                mapped.append((book, lat, lon))
        if not mapped:
            QMessageBox.information(
                self, "No Map Coordinates",
                "No books with valid latitude and longitude in the current view."
            )
            return
        try:
            import folium
            from folium.plugins import MarkerCluster
        except ImportError:
            QMessageBox.warning(
                self, "Folium Missing",
                "Install it with: python -m pip install folium"
            )
            return

        shown = mapped[:MAP_MARKER_LIMIT]
        center = [sum(m[1] for m in shown) / len(shown),
                  sum(m[2] for m in shown) / len(shown)]

        fmap = folium.Map(location=center, zoom_start=3, tiles=None)
        folium.TileLayer(
            tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
                   "World_Street_Map/MapServer/tile/{z}/{y}/{x}"),
            attr="Tiles (c) Esri", name="Street map"
        ).add_to(fmap)
        folium.TileLayer(
            tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
                   "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
            attr="Tiles (c) Esri", name="Satellite"
        ).add_to(fmap)
        folium.LayerControl().add_to(fmap)
        cluster = MarkerCluster().add_to(fmap)
        for book, lat, lon in shown:
            cover = html.escape(book.get("cover_url", ""))
            img = f"<img src='{cover}' width='80'><br>" if cover else ""
            text = (
                f"{img}<b>{html.escape(book.get('title', ''))}</b><br>"
                f"Author: {html.escape(book.get('author', ''))}<br>"
                f"Language: {html.escape(book.get('language', ''))}"
            )
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(text, max_width=240),
                tooltip=book.get("title", "")
            ).add_to(cluster)
        fmap.save(str(MAP_FILE))

        note = (f"Showing {len(shown):,} of {len(mapped):,} mapped books "
                "from the current view.")
        if len(mapped) > len(shown):
            note += " Filter the table to narrow it down."

        # keep a reference so the window is not garbage collected
        self.map_window = MapDialog(self, MAP_FILE, note)
        self.map_window.show()
        self.map_window.raise_()

    def closeEvent(self, event):
        if self.scraper is not None and self.scraper.isRunning():
            self.scraper.stop()
            self.scraper.wait(4000)
        self.persist()
        event.accept()


def main():
    # recommended by Qt when the web viewer is used
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLE)
    window = BooksApp()
    window.showMaximized()
    app.exec_()
    return window


if __name__ == "__main__":
    window = main()
# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

