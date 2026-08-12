"""Κανονικοποίηση ελληνικού κειμένου που προέρχεται από ΦΕΚ σε PDF.

Τα PDF του Εθνικού Τυπογραφείου έχουν συγκεκριμένες παθογένειες που, αν μείνουν
ανέπαφες, δηλητηριάζουν κάθε αναζήτηση πάνω στο corpus:

* **Ομόγραφοι λατινικοί χαρακτήρες.** Το Α, Β, Ε, Ο, Ρ, Τ κ.λπ. εμφανίζονται
  άλλοτε ως ελληνικά και άλλοτε ως λατινικά. Οπτικά ταυτόσημα, για τον υπολογιστή
  διαφορετικά — η αναζήτηση «ΑΡΘΡΟ» δεν βρίσκει το «APΘPO».
* **Το ∆ του μαθηματικού συμβόλου.** Πολλά ΦΕΚ κωδικοποιούν το κεφαλαίο δέλτα ως
  U+2206 INCREMENT αντί για U+0394 GREEK CAPITAL LETTER DELTA.
* **Συλλαβισμός στο τέλος γραμμής.** «κυκλοφο-\\nρίας» πρέπει να ξαναγίνει μία λέξη.
* **Κεφαλίδες και υποσέλιδα σελίδας** που παρεμβάλλονται μέσα στις προτάσεις.
* **Άτονα κεφαλαία** και ασυνεπής χρήση τελικού σίγμα.
"""

from __future__ import annotations

import re
import unicodedata

# ── Ομόγραφοι: λατινικό -> ελληνικό ────────────────────────────────────────
# Μόνο χαρακτήρες οπτικά ταυτόσημοι. Δεν αγγίζουμε γράμματα που διαφέρουν
# οπτικά, γιατί θα καταστρέφαμε γνήσια λατινικά κείμενα (π.χ. «ADR», «STOP»).
OMOGRAFOI_KEFALAIA = {
    "A": "Α", "B": "Β", "E": "Ε", "Z": "Ζ", "H": "Η", "I": "Ι", "K": "Κ",
    "M": "Μ", "N": "Ν", "O": "Ο", "P": "Ρ", "T": "Τ", "X": "Χ", "Y": "Υ",
}
OMOGRAFOI_PEZA = {"o": "ο", "v": "ν", "p": "ρ", "x": "χ"}

# ── Χαρακτήρες που πρέπει να αντικατασταθούν πάντα ─────────────────────────
ANTIKATASTASEIS = {
    "∆": "Δ",   # INCREMENT -> κεφαλαίο δέλτα
    "∑": "Σ",   # N-ARY SUMMATION -> κεφαλαίο σίγμα
    "Ω": "Ω",   # OHM SIGN -> ωμέγα (αν εμφανιστεί ως U+2126)
    "Ω": "Ω",
    "´": "΄",   # ACUTE ACCENT -> ελληνικό τονικό σημείο (για «Α΄»)
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "—",
    " ": " ",   # non-breaking space
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
}

# ── Θόρυβος σελίδας ΦΕΚ ────────────────────────────────────────────────────
# Οι κλάσεις χαρακτήρων καλύπτουν και τους λατινικούς ομόγραφους, επειδή ο
# θόρυβος αφαιρείται *πριν* τη διόρθωση ομογράφων.
MOTIVA_THORYVOU = [
    re.compile(
        r"^\s*ΕΦΗΜΕΡΙ[Δ∆]Α\s+[ΤT]ΗΣ\s+ΚΥΒΕΡΝΗΣΕΩΣ\s*$", re.IGNORECASE
    ),
    re.compile(r"^\s*ΕΦΗΜΕΡΙΣ\s+[ΤT]ΗΣ\s+ΚΥΒΕΡΝΗΣΕΩΣ\s*$", re.IGNORECASE),
    re.compile(r"^\s*Τε[υύ]χος\s+[Α-Ω]΄?\s*\d+\s*/\s*[\d.\-/]+\s*$", re.IGNORECASE),
    re.compile(r"^\s*ΕΘΝΙΚΟ\s+ΤΥΠΟΓΡΑΦΕΙΟ\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,6}\s*$"),                     # σκέτος αριθμός σελίδας
    re.compile(r"^\s*[-—]\s*\d{1,6}\s*[-—]\s*$"),       # «- 42 -»
    re.compile(r"^\s*$"),
]

# ── Αποτυπώματα νομικών βάσεων δεδομένων ───────────────────────────────────
# Οι εξαγωγές από τη βάση ΝΟΜΟΣ φέρνουν μαζί τους τον μηχανισμό της βάσης:
# «Αρθρο :12», «Πληροφορίες Νομολογίας & Αρθρογραφίας :3». Δεν είναι κείμενο
# του νόμου και δεν πρέπει να ακουστούν από φωνητικό πράκτορα.
#
# Ο δείκτης του άρθρου δεν διαγράφεται όμως — μεταφράζεται. Σε αυτές τις
# εξαγωγές η ίδια η επικεφαλίδα βρίσκεται συχνά στη μέση γραμμής, κολλημένη
# στο σχόλιο του προηγούμενου άρθρου («…(Α 98). Αρθρο :8 Προισχύσασες μορφές
# άρθρου :2 "Άρθρο 8»), οπότε ο αγωγός προσπερνούσε ολόκληρα άρθρα. Ο δείκτης
# της βάσης είναι εκεί ο μόνος αξιόπιστος δείκτης αρχής άρθρου.
DEIKTIS_ARTHROU = re.compile(r"[ΆΑ]ρθρο\s*:\s*(\d+)")
APOTYPOMATA_VASIS = [
    re.compile(r"Πληροφορίες\s+Νομολογίας\s*&\s*Αρθρογραφίας\s*:\s*\d+"),
    re.compile(r"Προισχύσασες\s+μορφές\s+άρθρου\s*:\s*\d+"),
    re.compile(r"Κατ['΄’]?\s*Εξουσιοδότηση\s+εκδοθείσα\s+Νομοθεσία\s*:\s*\d+"),
]
# Μετά τον δείκτη, το έγγραφο επαναλαμβάνει την επικεφαλίδα με τον δικό του
# τρόπο — «"Άρθρο 8», «Αρθρου 27», «"Αρθρο 34 Με απόφαση…». Η επανάληψη είναι
# περιττή και, όταν σέρνει μαζί της κείμενο, γίνεται ψευδής τίτλος.
EPANALIPSI_EPIKEFALIDAS = re.compile(
    r"(?m)^([ΆΑ]ρθρο (\d+))\n[ \t]*[\"'«]?[ \t]*[ΆΑ]ρθρο[νυΝΥ]?[ \t]+\2\s*[.:]?(?=\s|$)"
)

_SYLLAVISMOS = re.compile(r"(\w)[-­]\n(\w)", re.UNICODE)
_POLLA_KENA = re.compile(r"[ \t]{2,}")
_POLLES_GRAMMES = re.compile(r"\n{3,}")


def diorthose_omografous(keimeno: str) -> str:
    """Μετατρέπει λατινικούς ομόγραφους σε ελληνικούς, μόνο μέσα σε ελληνικές λέξεις.

    Η προϋπόθεση «μέσα σε ελληνική λέξη» είναι κρίσιμη: χωρίς αυτήν θα
    μετατρέπαμε το «STOP» σε «STΟΡ» και το «ADR» σε «ΑDR».
    """

    def antikatastasi_lexis(m: re.Match[str]) -> str:
        lexi = m.group(0)
        # Η λέξη θεωρείται ελληνική αν έχει τουλάχιστον έναν αναμφίβολα
        # ελληνικό χαρακτήρα (δηλαδή χωρίς λατινικό ομόγραφο).
        exei_elliniko = any(
            "Ͱ" <= ch <= "Ͽ" or "ἀ" <= ch <= "῿" for ch in lexi
        )
        if not exei_elliniko:
            return lexi
        return "".join(
            OMOGRAFOI_KEFALAIA.get(ch, OMOGRAFOI_PEZA.get(ch, ch)) for ch in lexi
        )

    return re.sub(r"[^\W\d_]+", antikatastasi_lexis, keimeno, flags=re.UNICODE)


def afairese_thoryvo_selidas(keimeno: str) -> str:
    """Πετάει κεφαλίδες, υποσέλιδα και αριθμούς σελίδας."""
    kratimenes = [
        gr
        for gr in keimeno.split("\n")
        if not any(m.match(gr) for m in MOTIVA_THORYVOU)
    ]
    return "\n".join(kratimenes)


def metafrase_deiktes_vasis(keimeno: str) -> str:
    """Μετατρέπει τα αποτυπώματα της βάσης σε κανονικές επικεφαλίδες άρθρων.

    Το «Αρθρο :0» δεν αντιστοιχεί σε άρθρο: η βάση βάζει εκεί το προοίμιο του
    νομοθετήματος. Γίνεται απλή αλλαγή γραμμής.
    """
    for motivo in APOTYPOMATA_VASIS:
        keimeno = motivo.sub("\n", keimeno)
    keimeno = DEIKTIS_ARTHROU.sub(
        lambda m: "\n" if m.group(1) == "0" else f"\nΆρθρο {m.group(1)}\n",
        keimeno,
    )
    return EPANALIPSI_EPIKEFALIDAS.sub(r"\1\n", keimeno)


def enose_syllavismo(keimeno: str) -> str:
    """«κυκλοφο-\\nρίας» -> «κυκλοφορίας»."""
    return _SYLLAVISMOS.sub(r"\1\2", keimeno)


def kanonikopoiise(keimeno: str, *, afairesi_thoryvou: bool = True) -> str:
    """Ο πλήρης αγωγός κανονικοποίησης, με τη σειρά που έχει σημασία.

    Ο συλλαβισμός ενώνεται *πριν* αφαιρεθεί ο θόρυβος σελίδας, ώστε μια λέξη
    κομμένη ακριβώς πάνω σε αλλαγή σελίδας να μην χάσει το δεύτερο μισό της.
    """
    keimeno = unicodedata.normalize("NFC", keimeno)
    for palio, neo in ANTIKATASTASEIS.items():
        keimeno = keimeno.replace(palio, neo)
    keimeno = enose_syllavismo(keimeno)
    if afairesi_thoryvou:
        keimeno = metafrase_deiktes_vasis(keimeno)
        keimeno = afairese_thoryvo_selidas(keimeno)
    keimeno = diorthose_omografous(keimeno)
    keimeno = _POLLA_KENA.sub(" ", keimeno)
    keimeno = _POLLES_GRAMMES.sub("\n\n", keimeno)
    return "\n".join(gr.rstrip() for gr in keimeno.split("\n")).strip()


def kleidi_anazitisis(keimeno: str) -> str:
    """Μορφή για σύγκριση και αναζήτηση: πεζά, χωρίς τόνους, χωρίς τελικό σίγμα.

    Επιτρέπει στο «ΚΥΚΛΟΦΟΡΊΑΣ», «κυκλοφορίας» και «κυκλοφοριας» να ταιριάξουν.
    """
    keimeno = unicodedata.normalize("NFD", keimeno.lower())
    keimeno = "".join(ch for ch in keimeno if not unicodedata.combining(ch))
    keimeno = unicodedata.normalize("NFC", keimeno)
    return keimeno.replace("ς", "σ")
