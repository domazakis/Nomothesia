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


def syndesmoi_apo_html(dedomena: bytes | str, vasi: str = "") -> list[tuple[str, str]]:
    """Οι σύνδεσμοι της σελίδας ως ζεύγη «κείμενο, απόλυτο URL».

    Χρησιμεύει στην ανίχνευση πηγών: όταν το επίσημο ΦΕΚ δεν κατεβαίνει,
    το ερώτημα «ποια σελίδα έχει αυτόν τον νόμο και πού δείχνει» απαντιέται
    πολύ πιο γρήγορα βλέποντας τους συνδέσμους μιας σελίδας παρά μαντεύοντας
    διευθύνσεις.
    """
    from urllib.parse import urljoin

    if isinstance(dedomena, bytes):
        dedomena = dedomena.decode("utf-8", "replace")

    evrethenta: list[tuple[str, str]] = []
    idonta: set[str] = set()
    for komvos in HTMLParser(dedomena).css("a[href]"):
        href = (komvos.attributes.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        pliris = urljoin(vasi, href) if vasi else href
        if pliris in idonta:
            continue
        idonta.add(pliris)
        evrethenta.append((" ".join(komvos.text().split()), pliris))
    return evrethenta
