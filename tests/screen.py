"""A terminal small enough to test against: it keeps what would be on screen."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"\x1b\[(\??[\d;]*)([A-Za-z])|\x1b\][^\x07]*\x07|[\s\S]")


class Screen:
    """A stream that acts on carriage returns, newlines, cursor-up and the two erases, and
    notes whether the cursor is hidden. Colours and other modes are accepted and ignored."""

    encoding = "utf-8"

    def __init__(self) -> None:
        self.rows: list[list[str]] = [[]]
        self.row = self.col = 0
        self.cursor_hidden = False
        self.raw = ""
        self.osc: list[str] = []

    def isatty(self) -> bool:
        return True

    def flush(self) -> None:
        pass

    def write(self, text: str) -> int:
        self.raw += text
        for match in _TOKEN.finditer(text):
            token = match.group(0)
            if token.startswith("\x1b]"):
                self.osc.append(token[2:-1])
            elif token.startswith("\x1b["):
                self._control(match.group(1), match.group(2))
            elif token == "\r":
                self.col = 0
            elif token == "\n":
                self.row += 1
                self.col = 0
                while len(self.rows) <= self.row:
                    self.rows.append([])
            else:
                line = self.rows[self.row]
                line.extend(" " * (self.col - len(line)))
                line[self.col : self.col + 1] = [token]
                self.col += 1
        return len(text)

    def _control(self, args: str, final: str) -> None:
        if final == "A":
            self.row = max(0, self.row - int(args or 1))
        elif final == "K":
            del self.rows[self.row][self.col :]
        elif final == "J":
            del self.rows[self.row][self.col :]
            del self.rows[self.row + 1 :]
        elif args == "?25":
            self.cursor_hidden = final == "l"

    def display(self) -> list[str]:
        """The lines on screen, without trailing blanks or trailing empty lines."""
        lines = ["".join(row).rstrip() for row in self.rows]
        while lines and not lines[-1]:
            lines.pop()
        return lines
