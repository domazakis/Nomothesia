"""Παραγωγή των αρχείων του corpus για ένα νομοθέτημα.

Κάθε νομοθέτημα παράγει τρία αρχεία στον φάκελό του:

* `full.md` — ολόκληρο το κείμενο σε Markdown. Για ανάγνωση από άνθρωπο και για
  να φαίνονται οι αλλαγές ως καθαρό git diff.
* `articles.jsonl` — μία εγγραφή ανά παράγραφο, με πλήρη μεταδεδομένα. Αυτό
  τροφοδοτεί την ανάκτηση του μελλοντικού agent.
* `meta.json` — ταυτότητα, προέλευση, checksum και ημερομηνία λήψης.

Ο διαχωρισμός δεν είναι διακοσμητικός: το `full.md` απαντά στο «τι λέει ο
νόμος», το `articles.jsonl` στο «ποια ακριβώς διάταξη το λέει».
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from nomothesia.normalize.structure import Arthro
from nomothesia.registry import Nomothetima

_ARXIKO = object()


def _epikefalida(n: Nomothetima, epalithevmeno: bool) -> list[str]:
    grammes = [
        f"# {n.onoma} — {n.titlos}",
        "",
        "| Πεδίο | Τιμή |",
        "| --- | --- |",
        f"| Αναγνωριστικό | `{n.id}` |",
        f"| Τύπος | {n.typos.value} |",
    ]
    if n.fek:
        grammes.append(f"| ΦΕΚ | {n.fek.anafora()} |")
    if n.celex:
        grammes.append(f"| CELEX | {n.celex} |")
    if n.isxys_apo:
        grammes.append(f"| Ισχύς από | {n.isxys_apo:%d-%m-%Y} |")
    grammes.append(f"| Κατάσταση | {n.katastasi.value} |")
    grammes.append(f"| Επαληθευμένο ΦΕΚ | {'ναι' if epalithevmeno else 'όχι'} |")
    grammes.extend(["", f"> {n.perigrafi.strip()}", ""])

    if n.katastasi.value != "isxyon":
        grammes.extend([
            "> [!WARNING]",
            "> **Δεν αποτελεί ισχύον δίκαιο.** Διατηρείται για ιστορικούς ή "
            "μεταβατικούς λόγους.",
            "",
        ])
    if not epalithevmeno:
        grammes.extend([
            "> [!CAUTION]",
            "> Τα στοιχεία ΦΕΚ δεν έχουν ακόμη αντιπαραβληθεί με το επίσημο "
            "αρχείο του Εθνικού Τυπογραφείου.",
            "",
        ])
    if n.simeioseis:
        grammes.extend(["**Σημειώσεις:** " + n.simeioseis.strip(), ""])

    return grammes


def grapse_full_md(
    n: Nomothetima,
    arthra: list[Arthro],
    fakelos: Path,
    *,
    epalithevmeno: bool | None = None,
) -> Path:
    grammes = _epikefalida(
        n, n.epalithevmeno if epalithevmeno is None else epalithevmeno
    )
    grammes.append("---")
    grammes.append("")

    # Ξεχωριστό αρχικό σήμα, ώστε το πρώτο άρθρο να τυπώνει επικεφαλίδα ακόμη
    # κι αν το Μέρος του είναι None.
    trexon_meros: object = _ARXIKO
    trexon_kefalaio: object = _ARXIKO

    for a in arthra:
        if a.meros != trexon_meros:
            trexon_meros = a.meros
            if a.meros:
                grammes.extend([f"## ΜΕΡΟΣ {a.meros}", ""])
        if a.kefalaio != trexon_kefalaio:
            trexon_kefalaio = a.kefalaio
            if a.kefalaio:
                grammes.extend([f"### ΚΕΦΑΛΑΙΟ {a.kefalaio}", ""])

        epikefalida = f"#### Άρθρο {a.arithmos}"
        if a.titlos:
            epikefalida += f" — {a.titlos}"
        grammes.extend([epikefalida, ""])

        for p in a.paragrafoi:
            grammes.append(f"{p.arithmos}. {p.keimeno}" if p.arithmos else p.keimeno)
            grammes.append("")

    diadromi = fakelos / "full.md"
    diadromi.write_text("\n".join(grammes).rstrip() + "\n", encoding="utf-8")
    return diadromi


def grapse_articles_jsonl(
    n: Nomothetima,
    arthra: list[Arthro],
    fakelos: Path,
    *,
    pigi_url: str,
    epalithevmeno: bool | None = None,
) -> Path:
    simera = dt.date.today().isoformat()
    epalithevthike = n.epalithevmeno if epalithevmeno is None else epalithevmeno
    diadromi = fakelos / "articles.jsonl"

    # Το αναγνωριστικό είναι το κλειδί της εγγραφής σε κάθε βάση ανάκτησης:
    # δύο εγγραφές με το ίδιο κλειδί σημαίνουν ότι η μία σβήνει την άλλη ή ότι
    # το ίδιο απόσπασμα μετράει διπλά. Στο π.δ. 237/1986 συνέβαινε επειδή η
    # πηγή παραθέτει και την παλιά και τη νέα γραφή μιας παραγράφου, οπότε το
    # άρθρο 5 είχε δύο παραγράφους «1». Η δεύτερη παίρνει κατάληξη· η πρώτη
    # μένει όπως ήταν, ώστε τα υπάρχοντα αναγνωριστικά να μην αλλάξουν.
    idomena: set[str] = set()

    with diadromi.open("w", encoding="utf-8") as f:
        for a in arthra:
            for p in a.paragrafoi:
                anagnoristiko = f"{n.id}:art-{a.arithmos}"
                if p.arithmos:
                    anagnoristiko += f":par-{p.arithmos}"
                if anagnoristiko in idomena:
                    seira = 2
                    while f"{anagnoristiko}-{seira}" in idomena:
                        seira += 1
                    anagnoristiko = f"{anagnoristiko}-{seira}"
                idomena.add(anagnoristiko)
                eggrafi = {
                    "id": anagnoristiko,
                    "nomothetima_id": n.id,
                    "nomothetima": n.onoma,
                    "titlos_nomothetimatos": n.titlos,
                    "thematiki": n.thematiki,
                    "arthro": a.arithmos,
                    "titlos_arthrou": a.titlos,
                    "paragrafos": p.arithmos,
                    "meros": a.meros.arithmisi if a.meros else None,
                    "meros_titlos": a.meros.titlos if a.meros else None,
                    "kefalaio": a.kefalaio.arithmisi if a.kefalaio else None,
                    "kefalaio_titlos": a.kefalaio.titlos if a.kefalaio else None,
                    "keimeno": p.keimeno,
                    "fek": n.fek.anafora() if n.fek else None,
                    "celex": n.celex,
                    "isxys_apo": n.isxys_apo.isoformat() if n.isxys_apo else None,
                    "katastasi": n.katastasi.value,
                    "epalithevmeno": epalithevthike,
                    "pigi_url": pigi_url,
                    "anaktithike": simera,
                }
                f.write(json.dumps(eggrafi, ensure_ascii=False) + "\n")

    return diadromi


def grapse_meta_json(
    n: Nomothetima,
    fakelos: Path,
    *,
    pigi_url: str,
    checksum_pigis: str,
    plithos_arthron: int,
    plithos_paragrafon: int,
    epalithevmeno: bool | None = None,
) -> Path:
    meta = {
        "id": n.id,
        "onoma": n.onoma,
        "titlos": n.titlos,
        "typos": n.typos.value,
        "thematiki": n.thematiki,
        "fek": n.fek.anafora() if n.fek else None,
        "fek_pdf_id": n.fek.pdf_id if n.fek else None,
        "celex": n.celex,
        "katastasi": n.katastasi.value,
        "isxys_apo": n.isxys_apo.isoformat() if n.isxys_apo else None,
        "epalithevmeno": n.epalithevmeno if epalithevmeno is None else epalithevmeno,
        "pigi_url": pigi_url,
        "checksum_pigis": checksum_pigis,
        "plithos_arthron": plithos_arthron,
        "plithos_paragrafon": plithos_paragrafon,
        "anaktithike": dt.date.today().isoformat(),
    }
    diadromi = fakelos / "meta.json"
    diadromi.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return diadromi
