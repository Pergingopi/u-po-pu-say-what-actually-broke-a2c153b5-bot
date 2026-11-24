#!/usr/bin/env python3
"""Say What Actually Broke - one line of software error copy.

Pure Python 3.13 standard library. The program writes one line of
error copy to /output/entry.txt. No network, no model call, fully
deterministic: the same code always writes the same bytes.

The line (110 characters, 110 bytes, no trailing newline):
    Error 500: the server didn't crash. It read your request,
    understood it perfectly, and refused to participate.

Gate (from the summary/rules): one line of software error copy, at
most 200 characters. The line is 110 characters, so it fits with
room to spare.

Trailing-newline decision: the file is written with NO trailing
newline, so the byte count is exactly the character count (110).
The gate says "at most 200 characters"; writing without the newline
keeps the counted length exactly equal to the line itself, so there
is no way a strict character count can read it as longer than the
line. A one-line text file without a trailing newline is still one
line: there is no second line of content.

Why this line (candidates compared against the brief: brutal truth
about the failure, makes the reader laugh, reads like real error
copy, one breath):

1. CHOSEN (kept by the reviser after re-testing alternatives):
   "Error 500: the server didn't crash. It read your request,
   understood it perfectly, and refused to participate."
   The brutal truth is that nothing broke by accident: the system
   understood the request and declined. It reads exactly like a
   status-page error, then turns on the user with a deadpan refusal.
   Short, quotable, one breath. "Perfectly" is load-bearing: full
   comprehension plus refusal is what makes it absurd.
2. "Something went wrong. Specifically, the code you deployed at
   4:59 PM on a Friday. It worked exactly as written." (111 chars)
   Relatable and true, but it is really two sentences plus a punch
   line, and the joke needs the reader to know deploy culture; the
   chosen line lands on anyone who has ever seen an Error 500.
3. "Error: nothing broke. The system worked exactly as written -
   which, given who wrote it, is the real problem." (108 chars)
   Same "worked as written" twist, but it points the finger at the
   author instead of staging a refusal; the chosen line's
   "refused to participate" is the funnier, more surprising turn.

Reviser re-checks (no candidate was clearly stronger, so the line
was kept and the program hardened instead):
- "Error 500: the server didn't crash. It read your request,
  understood it, and decided you weren't worth the effort."
  Direct-insult punch, but it breaks the deadpan error-copy voice;
  the server stops sounding like a system message.
- "Error 500: nothing broke. The server read your request,
  understood it perfectly, and went on strike."
  Vivid, but "went on strike" is a more familiar image than
  "refused to participate", which is the more original turn.
- "Error: your request was received, understood, and denied. The
  server is fine. You are the problem."
  Strong finger-pointing punch, but two stitched jokes instead of
  one clean setup-to-punch arc, and it drops the Error 500 frame.
- Dropping "perfectly" from the chosen line (102 chars) tightens
  it, but loses the emphasis that makes the refusal absurd.

Hardening (reviser): pre-write gate now also rejects any control
character (not just newline/CR) and leading/trailing whitespace;
the temp file is created with O_EXCL under a pid-suffixed name so
a stale temp can never be silently clobbered; the file is fsynced
before the atomic rename and the output directory is fsynced after
it; an empty MAKEFUN_OUTPUT_DIR falls back to /output; after the
rename the final file is read back and its bytes, length and mode
are asserted to match exactly what was intended.

Usage: mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os

LINE = (
    "Error 500: the server didn't crash. It read your request, "
    "understood it perfectly, and refused to participate."
)

MAX_CHARS = 200


def validate_line(text):
    """Check the line against the gate before anything is written.

    Raises AssertionError on the first failing check, so an invalid
    line can never be written to entry.txt by accident.
    """
    assert text and not text.isspace(), "line must not be blank"
    assert text == text.strip(), "line must not have leading/trailing whitespace"
    assert "\n" not in text and "\r" not in text, (
        "line must be a single line (no embedded newline)"
    )
    bad = [c for c in text if ord(c) < 0x20 or ord(c) == 0x7F]
    assert not bad, f"line must not contain control characters: {bad!r}"
    assert 1 <= len(text) <= MAX_CHARS, (
        f"line must be 1-{MAX_CHARS} characters, got {len(text)}"
    )
    text.encode("utf-8")  # raises UnicodeEncodeError if not UTF-8


def _fsync_dir(path):
    """Best-effort fsync of a directory (durability of the rename)."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def main():
    validate_line(LINE)
    out_dir = (os.environ.get("MAKEFUN_OUTPUT_DIR") or "").strip() or "/output"
    os.makedirs(out_dir, exist_ok=True)
    # No trailing newline: file bytes == the line itself (110 bytes).
    data = LINE.encode("utf-8")
    final = os.path.join(out_dir, "entry.txt")
    tmp = None
    fd = None
    for attempt in range(100):
        candidate = os.path.join(
            out_dir, f".entry.txt.tmp.{os.getpid()}.{attempt}"
        )
        try:
            fd = os.open(
                candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644
            )
        except FileExistsError:
            continue
        tmp = candidate
        break
    if fd is None:
        raise RuntimeError("could not create a unique temp file")
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.chmod(tmp, 0o644)
        os.replace(tmp, final)
        os.chmod(final, 0o644)
        _fsync_dir(out_dir)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    # Read-back: the finished file must be exactly the intended bytes.
    with open(final, "rb") as f:
        written = f.read()
    assert written == data, "read-back mismatch: entry.txt != intended bytes"
    assert len(written) == len(LINE), "read-back length mismatch"
    assert (os.stat(final).st_mode & 0o777) == 0o644, (
        "entry.txt mode is not 0644"
    )


if __name__ == "__main__":
    main()
