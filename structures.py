from collections import deque


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
