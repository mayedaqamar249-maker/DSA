import sys
import tkinter as tk

from app import SolitaireApp
from tests import run_tests


def main():
    if "--test" in sys.argv:
        sys.exit(0 if run_tests() else 1)
    root = tk.Tk()
    SolitaireApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
