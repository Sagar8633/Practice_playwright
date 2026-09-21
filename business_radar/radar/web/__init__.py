"""The browser layer: the only place a human decision becomes a database row.

Everything else in this package researches, scores and drafts. None of it may contact anybody.
The four safety invariants in docs/_CONTEXT.md section 3 are all, in the end, statements about
this package: an approval row is written by a session that a password created, the send control
exists in exactly one template, an eligibility re-check runs inside the send request rather than
being trusted from the page that drew the button, and every sentence in a message is traced back
to a stored finding before Sagar is shown it.

Without this package the system is a research tool with no gate. The gate is a person reading a
screen, and this is the screen.
"""

from __future__ import annotations

__all__ = ["create_app", "serve", "CONFIRMATION_TEXT"]


def __getattr__(name: str):  # pragma: no cover - thin lazy re-export
    if name in __all__:
        from . import app as _app

        return getattr(_app, name)
    raise AttributeError(name)
