"""Παραγωγή knowledge base για φωνητικό agent.

Το `corpus/` είναι φτιαγμένο για ακρίβεια: μια εγγραφή ανά παράγραφο, με πλήρη
μεταδεδομένα. Ένα knowledge base RAG θέλει κάτι άλλο — κείμενο που, όποια κι αν
είναι η τομή του chunker, κουβαλά μαζί του την ταυτότητά του.

Γι' αυτό κάθε άρθρο εδώ ξεκινά με επικεφαλίδα που λέει από πού προέρχεται. Αν η
τομή πέσει στη μέση του άρθρου 46, το κομμάτι που θα φτάσει στον agent
εξακολουθεί να έχει από πάνω του «Άρθρο 46 του Κώδικα Οδικής Κυκλοφορίας». Ο
agent μπορεί να πει πού το βρήκε — και σε ερώτηση νομοθεσίας, η παραπομπή είναι
το μισό της απάντησης.

Δύο επιλογές που κρίθηκαν σημαντικές:

* **Μόνο ισχύον δίκαιο.** Τα καταργημένα κείμενα μένουν στο `corpus/` για
  αναφορά αλλά δεν φτάνουν ποτέ στη φωνή. Ένας agent που απαντά με σιγουριά
  βάσει καταργημένου άρθρου δεν είναι ατελής, είναι λάθος.
* **Κείμενο για εκφώνηση.** Οι συντομογραφίες ανοίγουν, γιατί το «παρ. 2 περ.
  β΄» δεν διαβάζεται.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from nomothesia.normalize.ekfonisi import gia_ekfonisi
from nomothesia.registry import (
    Katastasi,
    Mitroo,
    Nomothetima,
    Typos,
    repo_riza,
)

MINES = (
    "Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου",
    "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου",
)


@dataclass
class ApotelesmaExport:
    nomothetima_id: str
    diadromi: Path
    plithos_arthron: int
    charaktires: int


def fakelos_export() -> Path:
    return repo_riza() / "export"


def _imerominia(imerominia) -> str:
    """«2025-06-13» → «13 Ιουνίου 2025», γιατί η φωνή δεν διαβάζει παύλες."""
    if imerominia is None:
        return ""
    return f"{imerominia.day} {MINES[imerominia.month - 1]} {imerominia.year}"


def _onoma_gia_foni(n: Nomothetima) -> str:
    """«Ν. 5209/2025» → «Νόμος 5209 του 2025».

    Το `onoma` του μητρώου είναι φτιαγμένο για πίνακες: σύντομο και γεμάτο
    τελείες. Εδώ χτίζεται από τα δομημένα πεδία, ώστε να βγει σε ονομαστική και
    ολογράφως — μια φωνή δεν διαβάζει «Ν.».
    """
    onomasia = {
        Typos.NOMOS: "Νόμος",
        Typos.PD: "Προεδρικό διάταγμα",
        Typos.YA: "Υπουργική απόφαση",
        Typos.KYA: "Κοινή υπουργική απόφαση",
        Typos.KANONISMOS_EE: "Κανονισμός της Ευρωπαϊκής Ένωσης",
        Typos.ODIGIA_EE: "Οδηγία της Ευρωπαϊκής Ένωσης",
    }[n.typos]
    if n.typos in (Typos.KANONISMOS_EE, Typos.ODIGIA_EE):
        return f"{onomasia} {gia_ekfonisi(str(n.arithmos))}"
    return f"{onomasia} {gia_ekfonisi(str(n.arithmos))} του {n.etos}"


def _teuxos_gia_foni(teuxos: str) -> str:
    """Το τεύχος του ΦΕΚ γράφεται λατινικά στο μητρώο· εδώ γίνεται ελληνικό."""
    return {
        "A": "Άλφα", "B": "Βήτα", "C": "Γάμμα", "D": "Δέλτα",
        "Α": "Άλφα", "Β": "Βήτα", "Γ": "Γάμμα", "Δ": "Δέλτα",
    }.get(teuxos.strip(), teuxos)


def _tautotita(n: Nomothetima) -> str:
    """Η προέλευση του κειμένου, σε μία πρόταση που διαβάζεται."""
    kommatia = [_onoma_gia_foni(n)]
    if n.fek:
        kommatia.append(
            f"ΦΕΚ τεύχος {_teuxos_gia_foni(n.fek.teuxos)}, "
            f"αριθμός {n.fek.arithmos}, {_imerominia(n.fek.imerominia)}"
        )
    if n.isxys_apo:
        kommatia.append(f"Ισχύει από {_imerominia(n.isxys_apo)}")
    return ". ".join(k for k in kommatia if k) + "."


def _arthra_apo_corpus(n: Nomothetima) -> list[dict]:
    """Διαβάζει το `articles.jsonl` και ομαδοποιεί τις παραγράφους ανά άρθρο."""
    diadromi = n.fakelos_corpus() / "articles.jsonl"
    if not diadromi.is_file():
        return []

    # Η ομαδοποίηση ακολουθεί τη σειρά του αρχείου και όχι λεξικό με κλειδί τον
    # αριθμό: ο ίδιος αριθμός άρθρου επανεμφανίζεται σε διαφορετικά Μέρη, και
    # ένα λεξικό θα τα συγχώνευε σιωπηλά σε ένα.
    arthra: list[dict] = []
    for grammi in diadromi.read_text(encoding="utf-8").splitlines():
        if not grammi.strip():
            continue
        eggrafi = json.loads(grammi)
        if not arthra or arthra[-1]["arithmos"] != eggrafi["arthro"]:
            arthra.append(
                {
                    "arithmos": eggrafi["arthro"],
                    "titlos": eggrafi.get("titlos_arthrou", ""),
                    "meros": eggrafi.get("meros_titlos", ""),
                    "kefalaio": eggrafi.get("kefalaio_titlos", ""),
                    "paragrafoi": [],
                }
            )
        arthra[-1]["paragrafoi"].append(
            (eggrafi.get("paragrafos", ""), eggrafi["keimeno"])
        )
    return arthra


def _keimeno_arthrou(n: Nomothetima, arthro: dict, tautotita: str) -> str:
    """Ένα άρθρο, με την ταυτότητά του από πάνω."""
    onoma = gia_ekfonisi(n.syntomos_titlos or n.onoma)
    titlos = gia_ekfonisi(arthro["titlos"]) if arthro["titlos"] else ""
    epikefalida = f"## {onoma} — Άρθρο {arthro['arithmos']}"
    if titlos:
        epikefalida += f": {titlos}"

    grammes = [epikefalida, "", tautotita]

    thesi = [
        gia_ekfonisi(t) for t in (arthro["meros"], arthro["kefalaio"]) if t
    ]
    if thesi:
        grammes.append(" — ".join(thesi))
    grammes.append("")

    for arithmos, keimeno in arthro["paragrafoi"]:
        eipomeno = gia_ekfonisi(keimeno)
        grammes.append(f"Παράγραφος {arithmos}. {eipomeno}" if arithmos else eipomeno)
        grammes.append("")

    return "\n".join(grammes)


def exagoge_nomothetimatos(n: Nomothetima) -> ApotelesmaExport | None:
    """Γράφει ένα αρχείο knowledge base για το νομοθέτημα, αν υπάρχει στο corpus."""
    arthra = _arthra_apo_corpus(n)
    if not arthra:
        return None

    tautotita = _tautotita(n)
    kommatia = [
        f"# {gia_ekfonisi(n.titlos)}",
        "",
        tautotita,
        "",
        gia_ekfonisi(n.perigrafi or ""),
        "",
    ]
    # Το όριο του κειμένου, όταν δεν φαίνεται διαβάζοντάς το. Στο π.δ.
    # 237/1986 είναι ότι τα άρθρα 11-24 φέρουν τη διατύπωση του 1986· χωρίς
    # αυτό, ο πράκτορας απαγγέλλει πρόστιμα σε δραχμές σαν να ισχύουν.
    # Οι `simeioseis` του μητρώου δεν έρχονται εδώ: είναι ημερολόγιο
    # συντηρητή, γεμάτο πιστοποιητικά και parsers, και δεν αφορούν κανέναν
    # που ρωτά για την ασφάλιση του αυτοκινήτου του.
    if n.prosochi:
        kommatia += ["## Προσοχή", "", gia_ekfonisi(n.prosochi), ""]
    kommatia += [_keimeno_arthrou(n, a, tautotita) for a in arthra]
    keimeno = "\n".join(kommatia).strip() + "\n"

    diadromi = fakelos_export() / n.thematiki / f"{n.id}.md"
    diadromi.parent.mkdir(parents=True, exist_ok=True)
    diadromi.write_text(keimeno, encoding="utf-8")

    return ApotelesmaExport(n.id, diadromi, len(arthra), len(keimeno))


def gia_knowledge_base(mitroo: Mitroo) -> list[Nomothetima]:
    """Μόνο το ισχύον δίκαιο. Τα καταργημένα δεν φτάνουν ποτέ στη φωνή."""
    return [
        n for n in mitroo.kata_proteraiotita() if n.katastasi is Katastasi.ISXYON
    ]
