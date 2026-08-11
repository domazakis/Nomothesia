"""Ανάλυση της δομής ενός νομοθετήματος: Μέρος → Κεφάλαιο → Άρθρο → παράγραφος.

Η ελληνική νομοτεχνική έχει σταθερή τυπολογία, την οποία εκμεταλλευόμαστε:

    ΜΕΡΟΣ Α΄
    ΓΕΝΙΚΕΣ ΔΙΑΤΑΞΕΙΣ

    ΚΕΦΑΛΑΙΟ Β΄
    ΚΑΝΟΝΕΣ ΚΥΚΛΟΦΟΡΙΑΣ

    Άρθρο 5
    Σήματα τροχονόμων

    1. Οι τροχονόμοι ρυθμίζουν την κυκλοφορία...
    2. Τα σήματα αυτά υπερισχύουν...

Η παράγραφος είναι η σωστή μονάδα ανάκτησης: ένα ολόκληρο άρθρο είναι συχνά
πολύ μεγάλο για να δοθεί ως απόσπασμα, ενώ μια πρόταση χάνει το νόημά της.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Ελληνική αρίθμηση με κεραία: Α΄, Β΄, ΙΑ΄ …
_ELLINIKO_NOUMERO = r"[Α-Ω]{1,4}[΄']?"
_LEKTIKO_NOUMERO = (
    r"ΠΡΩΤΟ|ΔΕΥΤΕΡΟ|ΤΡΙΤΟ|ΤΕΤΑΡΤΟ|ΠΕΜΠΤΟ|ΕΚΤΟ|ΕΒΔΟΜΟ|ΟΓΔΟΟ|ΕΝΑΤΟ|ΔΕΚΑΤΟ"
)

MEROS = re.compile(
    rf"^\s*ΜΕΡΟΣ\s+({_LEKTIKO_NOUMERO}|{_ELLINIKO_NOUMERO})\s*$",
    re.MULTILINE,
)
KEFALAIO = re.compile(
    rf"^\s*ΚΕΦΑΛΑΙΟ\s+({_LEKTIKO_NOUMERO}|{_ELLINIKO_NOUMERO})\s*$",
    re.MULTILINE,
)
# «Άρθρο 5», «ΑΡΘΡΟ 5», «Άρθρο 5Α», «Άρθρο 12 α»
ARTHRO = re.compile(
    r"^\s*[ΆΑ]ρθρο\s+(\d+)\s*([Α-Ωα-ω])?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
# «1.» ή «12.» στην αρχή γραμμής — αρχή παραγράφου
PARAGRAFOS = re.compile(r"^\s*(\d{1,3})\.\s+", re.MULTILINE)


@dataclass
class Paragrafos:
    arithmos: str
    keimeno: str


@dataclass
class Enotita:
    """Μέρος ή Κεφάλαιο: αρίθμηση και τίτλος."""

    arithmisi: str
    titlos: str = ""

    def __str__(self) -> str:
        return f"{self.arithmisi}΄ {self.titlos}".strip() if self.titlos else self.arithmisi


@dataclass
class Arthro:
    arithmos: str
    titlos: str = ""
    meros: Enotita | None = None
    kefalaio: Enotita | None = None
    paragrafoi: list[Paragrafos] = field(default_factory=list)

    @property
    def keimeno(self) -> str:
        return "\n\n".join(
            f"{p.arithmos}. {p.keimeno}" if p.arithmos else p.keimeno
            for p in self.paragrafoi
        )


def _enopoiise_grammes(keimeno: str) -> str:
    """Ενώνει τις σκληρές αλλαγές γραμμής της στοιχειοθεσίας σε ενιαία πρόταση.

    Στο ΦΕΚ η στήλη είναι στενή και οι προτάσεις σπάνε αυθαίρετα. Οι αλλαγές
    αυτές δεν φέρουν νόημα, και αν μείνουν, κάθε απόσπασμα που δίνεται ως
    παραπομπή βγαίνει κομματιασμένο.
    """
    return " ".join(gr.strip() for gr in keimeno.split("\n") if gr.strip())


def _spase_se_paragrafous(soma: str) -> list[Paragrafos]:
    """Κόβει το σώμα ενός άρθρου σε αριθμημένες παραγράφους.

    Κείμενο πριν από την «1.» (π.χ. εισαγωγική φράση) κρατιέται ως παράγραφος
    χωρίς αριθμό, ώστε να μη χαθεί.
    """
    soma = soma.strip()
    if not soma:
        return []

    theseis = list(PARAGRAFOS.finditer(soma))
    if not theseis:
        return [Paragrafos(arithmos="", keimeno=_enopoiise_grammes(soma))]

    paragrafoi: list[Paragrafos] = []

    prooimio = _enopoiise_grammes(soma[: theseis[0].start()])
    if prooimio:
        paragrafoi.append(Paragrafos(arithmos="", keimeno=prooimio))

    for i, m in enumerate(theseis):
        telos = theseis[i + 1].start() if i + 1 < len(theseis) else len(soma)
        keimeno = _enopoiise_grammes(soma[m.end() : telos])
        if keimeno:
            paragrafoi.append(Paragrafos(arithmos=m.group(1), keimeno=keimeno))

    return paragrafoi


def _titlos_meta_apo(keimeno: str, thesi: int) -> str:
    """Η πρώτη μη κενή γραμμή μετά τη θέση `thesi` — ο τίτλος μιας ενότητας.

    Σταματά αν συναντήσει άλλον δομικό δείκτη, ώστε ένα «ΜΕΡΟΣ Α΄» αμέσως
    πριν από «Άρθρο 1» να μην κλέψει τον τίτλο του άρθρου.
    """
    for grammi in keimeno[thesi:].split("\n")[:3]:
        katharh = grammi.strip()
        if not katharh:
            continue
        if MEROS.match(katharh) or KEFALAIO.match(katharh) or ARTHRO.match(katharh):
            return ""
        return katharh
    return ""


def analyse_domi(keimeno: str) -> list[Arthro]:
    """Επιστρέφει τα άρθρα του κειμένου, με το Μέρος και Κεφάλαιο στο οποίο ανήκουν.

    Το σώμα κάθε άρθρου κόβεται στον επόμενο **δομικό δείκτη οποιουδήποτε
    τύπου** — όχι μόνο στο επόμενο άρθρο. Διαφορετικά η επικεφαλίδα του
    επόμενου Κεφαλαίου θα κατέληγε προσκολλημένη στην τελευταία παράγραφο του
    προηγούμενου άρθρου.

    Δεν πετάει σφάλμα σε κείμενο χωρίς άρθρα — επιστρέφει κενή λίστα, ώστε ο
    καλών να αποφασίσει αν πρόκειται για πρόβλημα εξαγωγής ή για παράρτημα.
    """
    deiktes: list[tuple[int, int, str, re.Match[str]]] = []
    for eidos, motivo in (("meros", MEROS), ("kefalaio", KEFALAIO), ("arthro", ARTHRO)):
        for m in motivo.finditer(keimeno):
            deiktes.append((m.start(), m.end(), eidos, m))
    deiktes.sort(key=lambda d: d[0])

    if not any(d[2] == "arthro" for d in deiktes):
        return []

    arthra: list[Arthro] = []
    trexon_meros: Enotita | None = None
    trexon_kefalaio: Enotita | None = None

    for i, (_arxi, telos_deikti, eidos, m) in enumerate(deiktes):
        arithmisi = m.group(1).rstrip("΄'")
        epomeni_arxi = deiktes[i + 1][0] if i + 1 < len(deiktes) else len(keimeno)

        if eidos == "meros":
            trexon_meros = Enotita(arithmisi, _titlos_meta_apo(keimeno, telos_deikti))
            trexon_kefalaio = None  # νέο Μέρος μηδενίζει την αρίθμηση κεφαλαίων
            continue
        if eidos == "kefalaio":
            trexon_kefalaio = Enotita(arithmisi, _titlos_meta_apo(keimeno, telos_deikti))
            continue

        soma = keimeno[telos_deikti:epomeni_arxi]

        # Ο τίτλος του άρθρου είναι η πρώτη μη κενή γραμμή, εφόσον δεν είναι
        # ήδη αριθμημένη παράγραφος.
        titlos = ""
        grammes = soma.strip().split("\n")
        if grammes and grammes[0].strip() and not PARAGRAFOS.match(grammes[0]):
            titlos = grammes[0].strip()
            soma = "\n".join(grammes[1:])

        arthra.append(
            Arthro(
                arithmos=m.group(1) + (m.group(2).upper() if m.group(2) else ""),
                titlos=titlos,
                meros=trexon_meros,
                kefalaio=trexon_kefalaio,
                paragrafoi=_spase_se_paragrafous(soma),
            )
        )

    return arthra
