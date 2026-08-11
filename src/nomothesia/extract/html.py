"""Εξαγωγή κειμένου από κωδικοποιημένες σελίδες HTML και από το EUR-Lex."""

from __future__ import annotations

from selectolax.parser import HTMLParser

# Στοιχεία που δεν περιέχουν ποτέ νομοθετικό κείμενο.
ASCHETA = (
    "script", "style", "noscript", "nav", "header", "footer",
    "form", "button", "iframe", "svg",
)

# Πιθανοί υποδοχείς του κυρίως κειμένου, κατά σειρά προτίμησης.
YPODOCHEIS = (
    "#PP4Contents",        # EUR-Lex
    ".eli-main-content",   # EUR-Lex, νεότερη διάταξη
    "#docHtml",
    "article",
    "main",
    "#content",
    ".content",
)


def keimeno_apo_html(dedomena: bytes | str) -> str:
    """Επιστρέφει το κείμενο της σελίδας, χωρίς πλοήγηση και διαφημίσεις."""
    if isinstance(dedomena, bytes):
        dedomena = dedomena.decode("utf-8", "replace")
    domi = HTMLParser(dedomena)

    for epilogeas in ASCHETA:
        for komvos in domi.css(epilogeas):
            komvos.decompose()

    for epilogeas in YPODOCHEIS:
        if komvos := domi.css_first(epilogeas):
            return komvos.text(separator="\n", strip=True)

    return domi.body.text(separator="\n", strip=True) if domi.body else ""
