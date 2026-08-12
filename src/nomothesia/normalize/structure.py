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
# «Άρθρο 5», «ΑΡΘΡΟ 5», «Άρθρο 5Α», «Άρθρο 12 α», «Άρθρον 5.»
#
# Το τελικό «ν» δεν είναι λεπτομέρεια: οι νόμοι της δεκαετίας του '70 και του
# '80 γράφουν «Άρθρον», και χωρίς αυτό ο αγωγός δεν έβρισκε ούτε ένα άρθρο σε
# ολόκληρο τον ν. 489/1976 ή το π.δ. 237/1986 — κατέβαζε το κείμενο και το
# πετούσε. Το ίδιο και η τελεία μετά τον αριθμό, συνηθισμένη στην παλιά
# νομοτεχνική.
# Χωρίς IGNORECASE επίτηδες: μια επικεφαλίδα γράφεται πάντα «Άρθρο» ή «ΑΡΘΡΟ»,
# ποτέ «άρθρο». Το πεζό αρχικό είναι το σημάδι της παραπομπής μέσα σε πρόταση —
# και μια παραπομπή «…σύμφωνα με το άρθρο 57.» που τύχαινε να πέσει στην αρχή
# γραμμής έκοβε το άρθρο 57 του ΚΟΚ στα δύο.
# Το εισαγωγικό μπροστά δεν είναι σπάνιο: οι νομικές βάσεις τυπώνουν σε
# εισαγωγικά το κείμενο που αντικαταστάθηκε, και η επικεφαλίδα μπαίνει μέσα
# τους — «"Άρθρο 8». Χωρίς αυτό το άρθρο έμοιαζε ανύπαρκτο.
ARTHRO = re.compile(
    r"^\s*[\"'«]?\s*(?:[ΆΑ]ρθρο[νΝ]?|[ΆΑ]ΡΘΡΟ[Ν]?)\s+(\d+)\s*"
    r"([Α-Ωα-ω])?\s*[.:]?\s*[\"'»]?\s*$",
    re.MULTILINE,
)
# «1.» ή «12.» στην αρχή γραμμής — αρχή παραγράφου.
#
# Το κενό μετά την τελεία δεν είναι δεδομένο: ολόκληρος ο Τελωνειακός Κώδικας
# γράφει «1.Οι επιβάτες που…», και απαιτώντας το κενό ο αγωγός δεν έβρισκε
# καμία παράγραφο — το σώμα του άρθρου έμενε ενιαίο και η πρώτη του πρόταση
# περνούσε για τίτλο. Ο αριθμός μετά την τελεία όμως αποκλείεται: το «1.500
# ευρώ» στην αρχή γραμμής είναι ποσό, όχι παράγραφος.
PARAGRAFOS = re.compile(r"^\s*(\d{1,3})\.(?:[ \t]+|(?=\D))", re.MULTILINE)

# Οι τίτλοι σπάνε το πολύ σε τόσες σειρές· πέρα από αυτό διαβάζουμε σώμα.
MEGISTES_GRAMMES_TITLOU = 6

# Γραμμή τίτλου που τελειώνει έτσι δεν έχει τελειώσει: το ενωτικό χωρίζει τα
# σκέλη ενός σύνθετου τίτλου («… - Αντικατάσταση παρ. 3 άρθρου 12»).
SYNECHIZEI = ("-", ",", "—", "–")


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
    """Ο τίτλος μιας ενότητας: οι γραμμές μέχρι τον επόμενο δομικό δείκτη.

    Οι τίτλοι Μέρους και Κεφαλαίου τυπώνονται κεντραρισμένοι και σπάνε σε
    δεύτερη σειρά όταν δεν χωρούν — «ΣΗΜΑΝΣΗ - ΣΗΜΑΤΟΔΟΤΗΣΗ - / ΟΔΙΚΗ
    ΣΥΜΠΕΡΙΦΟΡΑ». Ανάμεσα σε δύο δομικούς δείκτες δεν υπάρχει τίποτε άλλο
    πέρα από τον τίτλο, οπότε τις ενώνουμε όλες.
    """
    grammes: list[str] = []
    for grammi in keimeno[thesi:].split("\n")[: MEGISTES_GRAMMES_TITLOU + 1]:
        katharh = grammi.strip()
        if not katharh:
            continue
        if MEROS.match(katharh) or KEFALAIO.match(katharh) or ARTHRO.match(katharh):
            break
        grammes.append(katharh)
    return _enose_titlo(grammes)


def _enose_titlo(grammes: list[str]) -> str:
    """Ενώνει τις γραμμές ενός τίτλου, χωρίς να διπλογράψει το ενωτικό."""
    titlos = ""
    for grammi in grammes:
        if not titlos:
            titlos = grammi
        elif titlos.endswith("-"):
            titlos = f"{titlos} {grammi}"
        else:
            titlos = f"{titlos} {grammi}"
    return titlos.strip()


def _titlos_arthrou(grammes: list[str]) -> int:
    """Πόσες από τις πρώτες γραμμές του άρθρου αποτελούν τον τίτλο του.

    Ο τίτλος τυπώνεται κεντραρισμένος και σπάει σε δεύτερη σειρά όταν δεν
    χωράει: «Οδήγηση υπό την επίδραση οινοπνεύματος, / φαρμάκων ή τοξικών
    ουσιών». Παίρνοντας μόνο την πρώτη γραμμή, ο μισός τίτλος κατέληγε στο
    σώμα του άρθρου ως παράγραφος — και το άρθρο για το αλκοόλ έδειχνε να
    λέει «φαρμάκων ή τοξικών ουσιών».

    Δύο ενδείξεις συνέχειας, και οι δύο συντηρητικές. Το **πεζό αρχικό
    γράμμα**: μια πρόταση του σώματος ξεκινά με κεφαλαίο ή με αριθμό
    παραγράφου, ενώ η συνέχεια ενός τίτλου συνεχίζει τη φράση. Και το
    **ενωτικό στο τέλος** της προηγούμενης γραμμής, που στους σύνθετους
    τίτλους των ΦΕΚ χωρίζει τα σκέλη («… - Αντικατάσταση παρ. 3»).

    Όταν ο τίτλος συνεχίζεται με κεφαλαίο χωρίς κανένα από τα δύο —συνήθως
    ορισμένος όρος όπως «Ελαφρών Προσωπικών / Ηλεκτρικών Οχημάτων»— μένει
    κομμένος. Δεν ξεχωρίζει με ασφάλεια από αρχή πρότασης, και προτιμότερο
    είναι ένας κολοβός τίτλος από ένα άρθρο που έχασε την πρώτη του πρόταση.
    """
    if not grammes or not grammes[0].strip() or PARAGRAFOS.match(grammes[0]):
        return 0

    plithos = 1
    for grammi in grammes[1 : MEGISTES_GRAMMES_TITLOU + 1]:
        katharh = grammi.strip()
        if not katharh or PARAGRAFOS.match(katharh):
            break
        proigoumeni = grammes[plithos - 1].strip()
        if not (katharh[0].islower() or proigoumeni.endswith(SYNECHIZEI)):
            break
        plithos += 1

    # Ένας τίτλος που δεν τελείωσε ποτέ δεν ήταν τίτλος. Όταν η συνέχεια
    # φτάνει ως το όριο και εξακολουθεί να συνεχίζεται, αυτό που διαβάζουμε
    # είναι η πρώτη πρόταση του σώματος: το άρθρο 1 του π.δ. 237/1986 άρχιζε
    # κατευθείαν με ορισμούς, και τριακόσιοι χαρακτήρες ορισμών γίνονταν
    # «τίτλος». Οι γνήσιοι τίτλοι, όσο μακροί κι αν είναι, σταματούν μόνοι.
    if plithos > MEGISTES_GRAMMES_TITLOU:
        return 0
    return plithos


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

        grammes = soma.strip().split("\n")
        plithos_titlou = _titlos_arthrou(grammes)
        titlos = _enose_titlo([g.strip() for g in grammes[:plithos_titlou]])
        if plithos_titlou:
            soma = "\n".join(grammes[plithos_titlou:])

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
