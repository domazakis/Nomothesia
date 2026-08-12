"""Εξαγωγή κειμένου από παλαιά δυαδικά αρχεία Word (`.doc`, Word 97-2003).

Ο ελληνικός δημόσιος τομέας εξακολουθεί να δημοσιεύει νομοθεσία σε αυτή τη
μορφή — και μερικές φορές είναι η **μόνη** αναγνώσιμη μορφή που απομένει, όταν
το ΦΕΚ είναι σαρωμένη εικόνα. Το π.δ. 237/1986 είναι ακριβώς τέτοια περίπτωση.

Η μορφή δεν είναι ZIP με XML μέσα (αυτό είναι το νεότερο `.docx`), αλλά OLE
compound file: ένα μικρό σύστημα αρχείων μέσα σε ένα αρχείο. Το κείμενο δεν
αποθηκεύεται σε συνεχόμενο κομμάτι — ζει διάσπαρτο μέσα στο stream
`WordDocument`, και ο **piece table** στο stream `0Table`/`1Table` λέει με ποια
σειρά διαβάζεται. Χωρίς αυτόν, ό,τι κι αν διαβάσει κανείς είναι ανακατεμένο ή
σκουπίδια.

Η υλοποίηση ακολουθεί την προδιαγραφή [MS-DOC]. Δεν προσπαθεί να αποδώσει
μορφοποίηση: μας ενδιαφέρει το κείμενο και οι αλλαγές παραγράφου, τίποτε άλλο.
"""

from __future__ import annotations

import io
import logging
import struct

import olefile

logger = logging.getLogger(__name__)

# Η υπογραφή ενός OLE compound file. Την έχουν και τα `.xls`/`.ppt` της ίδιας
# εποχής, γι' αυτό η τελική ετυμηγορία πέφτει μόνο αφού βρεθεί το `WordDocument`.
YPOGRAFI_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# Στην αρχή του FIB· αν λείπει, το stream δεν είναι έγγραφο Word.
YPOGRAFI_FIB = 0xA5EC
# Δείχνει ποιο από τα δύο table streams ισχύει — το άλλο είναι παλιό αντίγραφο.
SIMAIA_TABLE_STREAM = 0x0200
# Ελληνικό lid· καθορίζει τη σελίδα κώδικα του συμπιεσμένου κειμένου.
LID_ELLINIKA = 0x0408

# Δείκτες μέσα στο Clx (piece table).
PRC = 0x01
PLCFPCD = 0x02
# Κάθε PCD είναι 8 bytes, κάθε CP 4· ένα κομμάτι κοστίζει 12.
MEGETHOS_PCD = 8
MEGETHOS_CP = 4
# Το bit που λέει «το κείμενο αυτού του κομματιού είναι 8-bit, όχι UTF-16».
SYMPIESMENO = 0x40000000
MASKA_FC = 0x3FFFFFFF


class SfalmaDoc(ValueError):
    """Το αρχείο δεν είναι αναγνώσιμο έγγραφο Word 97-2003."""


def einai_doc(dedomena: bytes) -> bool:
    """Αληθές μόνο για παλαιά δυαδικά `.doc`, όχι για κάθε OLE αρχείο."""
    if dedomena[:8] != YPOGRAFI_OLE:
        return False
    try:
        with olefile.OleFileIO(io.BytesIO(dedomena)) as ole:
            return ole.exists("WordDocument")
    except Exception:
        return False


def keimeno_apo_doc(dedomena: bytes) -> str:
    """Επιστρέφει το κείμενο του κυρίως σώματος του εγγράφου.

    Υποσημειώσεις, κεφαλίδες και υποσέλιδα μένουν έξω επίτηδες: στα ΦΕΚ και
    στις αναδημοσιεύσεις τους περιέχουν αρίθμηση σελίδων και τίτλους τεύχους,
    δηλαδή θόρυβο που θα έσπαγε την ανίχνευση άρθρων.

    Δεν κάνει κανονικοποίηση — αυτή είναι δουλειά του `normalize.greek`.
    """
    with olefile.OleFileIO(io.BytesIO(dedomena)) as ole:
        if not ole.exists("WordDocument"):
            raise SfalmaDoc("το αρχείο OLE δεν περιέχει stream «WordDocument»")
        egrafo = ole.openstream("WordDocument").read()
        onoma = _onoma_pinaka(egrafo)
        if not ole.exists(onoma):
            raise SfalmaDoc(f"λείπει το stream «{onoma}» με τον piece table")
        pinakas = ole.openstream(onoma).read()

    return keimeno_apo_streams(egrafo, pinakas)


def keimeno_apo_streams(egrafo: bytes, pinakas: bytes) -> str:
    """Το ίδιο, με τα δύο streams ήδη διαβασμένα.

    Χωριστή συνάρτηση ώστε η ανάλυση της μορφής να ελέγχεται χωρίς να χρειάζεται
    να κατασκευαστεί ολόκληρο OLE αρχείο.
    """
    if len(egrafo) < 4 or _u16(egrafo, 0) != YPOGRAFI_FIB:
        raise SfalmaDoc("το stream «WordDocument» δεν αρχίζει με έγκυρο FIB")

    theseis = _theseis_fib(egrafo)
    fc_clx = _u32(egrafo, theseis["fcClx"])
    lcb_clx = _u32(egrafo, theseis["lcbClx"])
    if not lcb_clx or fc_clx + lcb_clx > len(pinakas):
        raise SfalmaDoc("ο piece table λείπει ή δείχνει εκτός ορίων")

    kodikoselida = "cp1253" if _u16(egrafo, 6) == LID_ELLINIKA else "cp1252"
    kommatia = _kommatia(pinakas[fc_clx : fc_clx + lcb_clx])

    # Το κυρίως σώμα είναι οι πρώτοι `ccpText` χαρακτήρες· ό,τι ακολουθεί είναι
    # υποσημειώσεις, σχόλια και κεφαλίδες, με τη σειρά που ορίζει το FIB.
    plithos_kyrios = _u32(egrafo, theseis["ccpText"])

    grafto: list[str] = []
    for arxi_cp, telos_cp, fc, sympiesmeno in kommatia:
        if arxi_cp >= plithos_kyrios:
            break
        plithos = min(telos_cp, plithos_kyrios) - arxi_cp
        if plithos <= 0:
            continue
        grafto.append(_apokodikopoiise(egrafo, fc, plithos, sympiesmeno, kodikoselida))

    return _katharo("".join(grafto))


def _onoma_pinaka(egrafo: bytes) -> str:
    """Ποιο από τα δύο table streams είναι το ενεργό.

    Τα έγγραφα κρατούν και τα δύο· διαβάζοντας το λάθος, ο piece table δείχνει
    σε παλιές θέσεις και το κείμενο βγαίνει κομματιασμένο.
    """
    return "1Table" if _u16(egrafo, 0x0A) & SIMAIA_TABLE_STREAM else "0Table"


def _theseis_fib(egrafo: bytes) -> dict[str, int]:
    """Πού βρίσκονται τα πεδία του FIB που μας ενδιαφέρουν.

    Τα μεγέθη των τμημάτων δηλώνονται μέσα στο ίδιο το FIB αντί να είναι
    σταθερά, ώστε η δομή να μεγαλώνει σε νεότερες εκδόσεις. Τα διαβάζουμε
    αντί να υποθέσουμε τις γνωστές τιμές (0x01A2 κ.λπ.): έτσι το ίδιο
    διάβασμα δουλεύει και σε παραλλαγές που δεν έχουμε δει.
    """
    csw = _u16(egrafo, 0x20)
    thesi_cslw = 0x22 + csw * 2
    cslw = _u16(egrafo, thesi_cslw)
    thesi_fib_rg_lw = thesi_cslw + 2
    thesi_cb_rg_fc_lcb = thesi_fib_rg_lw + cslw * 4
    thesi_blob = thesi_cb_rg_fc_lcb + 2

    theseis = {
        "ccpText": thesi_fib_rg_lw + 12,
        # 34ο ζεύγος fc/lcb μέσα στο FibRgFcLcb97.
        "fcClx": thesi_blob + 33 * 8,
        "lcbClx": thesi_blob + 33 * 8 + 4,
    }
    if theseis["lcbClx"] + 4 > len(egrafo):
        raise SfalmaDoc("το FIB είναι κολοβό — δεν φτάνει ως τον piece table")
    return theseis


def _kommatia(clx: bytes) -> list[tuple[int, int, int, bool]]:
    """Ο piece table: πού ζει και πώς κωδικοποιείται κάθε κομμάτι κειμένου.

    Επιστρέφει τετράδες (πρώτος χαρακτήρας, τελευταίος, θέση στο stream,
    συμπιεσμένο).
    """
    thesi = 0
    # Πριν από τον πίνακα μπορεί να προηγούνται ομάδες ιδιοτήτων μορφοποίησης.
    # Δεν μας αφορούν· μας αφορά μόνο το μήκος τους, για να τις προσπεράσουμε.
    while thesi < len(clx) and clx[thesi] == PRC:
        thesi += 3 + struct.unpack_from("<h", clx, thesi + 1)[0]
    if thesi >= len(clx) or clx[thesi] != PLCFPCD:
        raise SfalmaDoc("δεν βρέθηκε piece table μέσα στο Clx")

    mikos = _u32(clx, thesi + 1)
    plc = clx[thesi + 5 : thesi + 5 + mikos]
    plithos = (len(plc) - MEGETHOS_CP) // (MEGETHOS_CP + MEGETHOS_PCD)
    if plithos <= 0:
        raise SfalmaDoc("ο piece table είναι κενός")

    arxi_pcd = MEGETHOS_CP * (plithos + 1)
    kommatia = []
    for k in range(plithos):
        arxi_cp = _u32(plc, MEGETHOS_CP * k)
        telos_cp = _u32(plc, MEGETHOS_CP * (k + 1))
        akatergasto_fc = _u32(plc, arxi_pcd + MEGETHOS_PCD * k + 2)
        sympiesmeno = bool(akatergasto_fc & SYMPIESMENO)
        fc = akatergasto_fc & MASKA_FC
        # Στα συμπιεσμένα κομμάτια η θέση είναι γραμμένη σε διπλάσια κλίμακα,
        # γιατί το πεδίο σχεδιάστηκε για χαρακτήρες των δύο bytes.
        kommatia.append((arxi_cp, telos_cp, fc // 2 if sympiesmeno else fc, sympiesmeno))
    return kommatia


def _apokodikopoiise(
    egrafo: bytes, fc: int, plithos: int, sympiesmeno: bool, kodikoselida: str
) -> str:
    """Ένα κομμάτι κειμένου, από bytes σε χαρακτήρες.

    Η σελίδα κώδικα του συμπιεσμένου κειμένου δεν γράφεται πουθενά ρητά — την
    υπαγορεύει η γλώσσα του εγγράφου. Για ελληνικό έγγραφο αυτό σημαίνει
    cp1253· διαβασμένο ως cp1252 το κείμενο βγαίνει λατινικά σύμβολα.
    """
    if sympiesmeno:
        return egrafo[fc : fc + plithos].decode(kodikoselida, errors="replace")
    return egrafo[fc : fc + plithos * 2].decode("utf-16-le", errors="replace")


# Οι χαρακτήρες ελέγχου του Word: τι σημαίνει ο καθένας για το απλό κείμενο.
TELOS_PARAGRAFOU = "\r\x0b\x0c\x07"
APORRIPTOMENOI = "\x01\x02\x03\x04\x05\x06\x08\x1f"
ANTIKATASTASEIS = {"\x1e": "-", "\xa0": " ", "\t": " "}
# Ένα πεδίο («σελίδα Χ από Υ», σύνδεσμοι) γράφεται ως οδηγία μέσα σε 0x13…0x14
# και αποτέλεσμα ως 0x14…0x15. Η οδηγία δεν είναι κείμενο του νόμου.
ARXI_PEDIOU = "\x13"
CHORISMA_PEDIOU = "\x14"
TELOS_PEDIOU = "\x15"


def _katharo(akatergasto: str) -> str:
    """Μετατρέπει τους χαρακτήρες ελέγχου του Word σε απλό κείμενο."""
    grammata: list[str] = []
    mesa_se_odigia = False
    for charaktiras in akatergasto:
        if charaktiras == ARXI_PEDIOU:
            mesa_se_odigia = True
        elif charaktiras in (CHORISMA_PEDIOU, TELOS_PEDIOU):
            mesa_se_odigia = False
        elif mesa_se_odigia or charaktiras in APORRIPTOMENOI:
            continue
        elif charaktiras in TELOS_PARAGRAFOU:
            grammata.append("\n")
        else:
            grammata.append(ANTIKATASTASEIS.get(charaktiras, charaktiras))
    return "".join(grammata)


def _u16(dedomena: bytes, thesi: int) -> int:
    return struct.unpack_from("<H", dedomena, thesi)[0]


def _u32(dedomena: bytes, thesi: int) -> int:
    return struct.unpack_from("<I", dedomena, thesi)[0]
