"""Ο αγωγός: λήψη → εξαγωγή → κανονικοποίηση → δομή → αρχεία corpus."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from nomothesia.extract.doc import einai_doc, keimeno_apo_doc
from nomothesia.extract.html import keimeno_apo_html
from nomothesia.extract.pdf import exei_epipedo_keimenou, keimeno_apo_pdf
from nomothesia.fetch.base import Lipsi, SfalmaLipsis
from nomothesia.normalize.emit import (
    grapse_articles_jsonl,
    grapse_full_md,
    grapse_meta_json,
)
from nomothesia.normalize.greek import kanonikopoiise, kleidi_anazitisis
from nomothesia.normalize.structure import Arthro, analyse_domi
from nomothesia.registry import Nomothetima, Typos, TyposPigis

logger = logging.getLogger(__name__)

# Ποια πηγή προτιμάμε ανά τύπο νομοθετήματος. Το επίσημο ΦΕΚ προηγείται πάντα
# των κωδικοποιημένων εκδόσεων τρίτων.
PROTERAIOTITA_PIGON: dict[Typos, tuple[TyposPigis, ...]] = {
    Typos.KANONISMOS_EE: (TyposPigis.EURLEX_HTML,),
    Typos.ODIGIA_EE: (TyposPigis.EURLEX_HTML,),
}
# Το ζωντανό ΦΕΚ προηγείται του τοπικού αντιγράφου, ώστε η επίσημη πηγή να
# ξαναδοκιμάζεται σε κάθε εκτέλεση και να επανέλθει μόνη της όταν διορθωθεί.
# Το αντίγραφο έπεται αμέσως: είναι το ίδιο έγγραφο, όχι κωδικοποίηση τρίτου.
PROTERAIOTITA_EX_ORISMOU = (
    TyposPigis.FEK_PDF,
    TyposPigis.TOPIKO_FEK,
    TyposPigis.KODIKOPOIIMENO_HTML,
    TyposPigis.PDF_ALLI_PIGI,
    TyposPigis.DOC_ALLI_PIGI,
)


class SfalmaAgogou(RuntimeError):
    """Ο αγωγός δεν μπόρεσε να παραγάγει corpus για ένα νομοθέτημα."""


@dataclass
class ApotelesmaAgogou:
    nomothetima_id: str
    pigi_url: str
    plithos_arthron: int
    plithos_paragrafon: int
    checksum_pigis: str
    checksum_keimenou: str
    epalithevmeno_fek: bool
    proeidopoiiseis: list[str]


def _seira_pigon(n: Nomothetima) -> list:
    """Όλες οι πηγές του νομοθετήματος, με την προτιμώμενη πρώτη.

    Επιστρέφει σειρά και όχι μία πηγή, γιατί οι εναλλακτικές υπάρχουν ακριβώς
    για να χρησιμοποιηθούν: το et.gr πέφτει, μπλοκάρει διευθύνσεις ή αλλάζει
    endpoint, και τότε η κωδικοποιημένη έκδοση είναι προτιμότερη από το τίποτα.
    """
    ypopsifies = [p for p in n.piges if p.typos is not TyposPigis.SYMPLIROMA]
    seira = PROTERAIOTITA_PIGON.get(n.typos, PROTERAIOTITA_EX_ORISMOU)
    taxinomimenes = [pigi for typos in seira for pigi in ypopsifies if pigi.typos is typos]
    ypoloipes = [pigi for pigi in ypopsifies if pigi not in taxinomimenes]
    if not (taxinomimenes or ypoloipes):
        raise SfalmaAgogou(f"{n.id}: καμία διαθέσιμη πηγή")
    return taxinomimenes + ypoloipes


def _epalithefse_fek(n: Nomothetima, akatergasto: str) -> bool:
    """Ελέγχει ότι το κατεβασμένο ΦΕΚ είναι όντως αυτό που περιμέναμε.

    Χωρίς αυτόν τον έλεγχο, ένα λάθος `pdf_id` στο μητρώο θα περνούσε αθόρυβα
    και θα γέμιζε το corpus με άσχετο νομοθέτημα.

    Δουλεύει πάνω στο **ακατέργαστο** κείμενο επίτηδες: τα στοιχεία που ψάχνουμε
    ζουν ακριβώς στην κεφαλίδα σελίδας («Τεύχος Α΄100/13.06.2025»), την οποία η
    κανονικοποίηση αφαιρεί ως θόρυβο.
    """
    if n.fek is None:
        return False
    arxi = kleidi_anazitisis(
        kanonikopoiise(akatergasto[:8000], afairesi_thoryvou=False)
    )
    return str(n.fek.arithmos) in arxi and str(n.fek.imerominia.year) in arxi


def _filtrare_arthra(n: Nomothetima, arthra: list[Arthro]) -> list[Arthro]:
    """Κρατά μόνο τα σχετικά άρθρα, όταν το μητρώο τα προσδιορίζει.

    Χρήσιμο για νόμους γενικού περιεχομένου, όπου λίγα μόνο άρθρα αφορούν την
    οδήγηση (π.χ. τα άρθρα 73-81 του ν. 5322/2026).
    """
    if not n.relevanta_arthra:
        return arthra
    zitoumena = {str(a) for a in n.relevanta_arthra}
    return [a for a in arthra if a.arithmos.rstrip("ΑΒΓΔΕ") in zitoumena]


def epexergasou(
    n: Nomothetima, lipsi: Lipsi, *, agnoise_cache: bool = False
) -> ApotelesmaAgogou:
    """Τρέχει τον αγωγό για ένα νομοθέτημα και γράφει τα αρχεία του.

    Δοκιμάζει τις πηγές με τη σειρά προτίμησης και σταματά στην πρώτη που
    αποδίδει κείμενο με άρθρα. Η πτώση σε εναλλακτική πηγή καταγράφεται ως
    προειδοποίηση: το κείμενο είναι χρήσιμο, αλλά δεν προέρχεται από το ΦΕΚ.
    """
    apotyxies: list[tuple[str, str]] = []

    for seira, pigi in enumerate(_seira_pigon(n)):
        try:
            apotelesma = _apo_pigi(n, pigi, lipsi, agnoise_cache=agnoise_cache)
        except SfalmaAgogou as exc:
            apotyxies.append((pigi.typos.value, str(exc)))
            continue

        if seira:
            apotelesma.proeidopoiiseis.insert(0, _minima_ptosis(pigi))
        return apotelesma

    if len(apotyxies) == 1:
        raise SfalmaAgogou(f"{n.id}: {apotyxies[0][1]}")
    perigrafes = "; ".join(f"{typos}: {minima}" for typos, minima in apotyxies)
    raise SfalmaAgogou(
        f"{n.id}: καμία από τις {len(apotyxies)} πηγές δεν απέδωσε κείμενο — "
        f"{perigrafes}"
    )


def _minima_ptosis(pigi) -> str:
    """Τι σημαίνει για τον αναγνώστη ότι χρησιμοποιήθηκε εναλλακτική πηγή.

    Το τοπικό αντίγραφο ΦΕΚ ξεχωρίζει: το κείμενο εξακολουθεί να είναι το
    επίσημο, απλώς δεν κατέβηκε τώρα. Μια κωδικοποίηση τρίτου είναι άλλο
    πράγμα και δεν πρέπει να τα μπερδεύει κανείς.
    """
    if pigi.typos is TyposPigis.TOPIKO_FEK:
        return (
            "το et.gr δεν απάντησε — το κείμενο προέρχεται από το αντίγραφο "
            f"ΦΕΚ του repository ({pigi.url}), που είναι το ίδιο έγγραφο"
        )
    return (
        f"η προτιμώμενη πηγή απέτυχε — το κείμενο προέρχεται από "
        f"{pigi.typos.value} ({pigi.url})"
    )


def _me_sympliromata(
    n: Nomothetima, arthra: list[Arthro], lipsi: Lipsi, proeidopoiiseis: list[str]
) -> list[Arthro]:
    """Προσθέτει τα άρθρα που λείπουν από την κύρια πηγή.

    Καμία πηγή του π.δ. 237/1986 δεν δίνει και τα πενήντα οκτώ άρθρα του: το
    μόνο αντίγραφο που κατεβαίνει σταματά στο δέκα και ξαναρχίζει στο είκοσι
    πέντε. Το συμπλήρωμα καλύπτει το κενό χωρίς να αντικαταστήσει την κύρια
    πηγή, η οποία παραμένει καλύτερη για όσα άρθρα έχει.

    Γι' αυτό ακριβώς ό,τι ήδη υπάρχει **δεν** αντικαθίσταται: το συμπλήρωμα
    γεμίζει τρύπες, δεν ξαναγράφει άρθρα.
    """
    sympliromata = [p for p in n.piges if p.typos is TyposPigis.SYMPLIROMA]
    if not sympliromata:
        return arthra

    yparxonta = {a.arithmos for a in arthra}
    prostheta: list[Arthro] = []
    for pigi in sympliromata:
        try:
            apotelesma = lipsi.kateveste(pigi.url)
        except SfalmaLipsis as exc:
            proeidopoiiseis.append(f"το συμπλήρωμα {pigi.url} δεν διαβάστηκε: {exc}")
            continue
        keimeno = kanonikopoiise(apotelesma.perieksomeno.decode("utf-8"))
        nea = [a for a in analyse_domi(keimeno) if a.arithmos not in yparxonta]
        yparxonta.update(a.arithmos for a in nea)
        prostheta.extend(nea)

    if not prostheta:
        return arthra

    proeidopoiiseis.append(
        "άρθρα από συμπλήρωμα, όχι από την κύρια πηγή: "
        + ", ".join(a.arithmos for a in prostheta)
    )
    # Η σειρά του εγγράφου δεν ισχύει πια — τα συμπληρωμένα άρθρα θα έμεναν
    # στο τέλος. Ταξινομούνται αριθμητικά, με το γράμμα (17Α) μετά το σκέτο.
    return sorted(arthra + prostheta, key=_kleidi_seiras)


def _kleidi_seiras(a: Arthro) -> tuple[int, str]:
    arithmitiko = "".join(ch for ch in a.arithmos if ch.isdigit())
    return (int(arithmitiko) if arithmitiko else 0, a.arithmos)


def _apo_pigi(
    n: Nomothetima, pigi, lipsi: Lipsi, *, agnoise_cache: bool
) -> ApotelesmaAgogou:
    """Ολόκληρος ο αγωγός πάνω σε **μία** πηγή. Σφάλμα σημαίνει «δοκίμασε άλλη»."""
    proeidopoiiseis: list[str] = []

    try:
        apotelesma = lipsi.kateveste(pigi.url, agnoise_cache=agnoise_cache)
    except SfalmaLipsis as exc:
        raise SfalmaAgogou(str(exc)) from exc

    if apotelesma.einai_pdf:
        if not exei_epipedo_keimenou(apotelesma.perieksomeno):
            raise SfalmaAgogou(
                "το PDF δεν έχει επίπεδο κειμένου (σαρωμένο). "
                "Χρειάζεται OCR — εγκατάσταση με `pip install 'nomothesia[ocr]'`."
            )
        akatergasto = keimeno_apo_pdf(apotelesma.perieksomeno)
    elif einai_doc(apotelesma.perieksomeno):
        akatergasto = keimeno_apo_doc(apotelesma.perieksomeno)
    else:
        akatergasto = keimeno_apo_html(apotelesma.perieksomeno)

    keimeno = kanonikopoiise(akatergasto)
    if not keimeno.strip():
        # Το μέγεθος ξεχωρίζει το «κατέβηκε σελίδα σφάλματος» από το «κατέβηκε ο
        # νόμος και δεν ξέρουμε να τον διαβάσουμε». Χωρίς αυτό, τα δύο μοιάζουν.
        raise SfalmaAgogou(
            f"δεν εξήχθη καθόλου κείμενο από {pigi.url} "
            f"({len(apotelesma.perieksomeno)} bytes, "
            f"{apotelesma.typos_perieksomenou or 'άγνωστος τύπος'})"
        )

    epalithevmeno = _epalithefse_fek(n, akatergasto)
    if n.fek and not epalithevmeno:
        proeidopoiiseis.append(
            "τα στοιχεία ΦΕΚ δεν εντοπίστηκαν στην αρχή του κειμένου — "
            "ελέγξτε το pdf_id στο registry.yaml"
        )

    arthra = _filtrare_arthra(n, analyse_domi(keimeno))
    if not arthra:
        raise SfalmaAgogou(
            "δεν εντοπίστηκε κανένα άρθρο. Πιθανή αιτία: αλλαγή "
            "διάταξης στην πηγή ή λάθος URL."
        )

    # Μετά τον έλεγχο, ποτέ πριν. Το συμπλήρωμα προσθέτει σε πηγή που πέτυχε·
    # αν εφαρμοζόταν νωρίτερα, θα κρατούσε ζωντανή μια πηγή που δεν απέδωσε
    # τίποτα. Ακριβώς αυτό συνέβη: η κωδικοποιημένη σελίδα του π.δ. 237/1986
    # είναι πίσω από συνδρομή και δίνει μηδέν άρθρα, αλλά με τα δεκατέσσερα
    # του συμπληρώματος έμοιαζε επιτυχημένη — και ο αγωγός δεν έφτασε ποτέ
    # στο αντίγραφο Word που έχει τα υπόλοιπα σαράντα τέσσερα.
    arthra = _me_sympliromata(n, arthra, lipsi, proeidopoiiseis)

    fakelos = n.fakelos_corpus()
    fakelos.mkdir(parents=True, exist_ok=True)

    plithos_paragrafon = sum(len(a.paragrafoi) for a in arthra)
    grapse_full_md(n, arthra, fakelos, epalithevmeno=epalithevmeno)
    grapse_articles_jsonl(
        n, arthra, fakelos, pigi_url=pigi.url, epalithevmeno=epalithevmeno
    )
    grapse_meta_json(
        n,
        fakelos,
        pigi_url=pigi.url,
        checksum_pigis=apotelesma.checksum,
        plithos_arthron=len(arthra),
        plithos_paragrafon=plithos_paragrafon,
        epalithevmeno=epalithevmeno,
    )

    return ApotelesmaAgogou(
        nomothetima_id=n.id,
        pigi_url=pigi.url,
        plithos_arthron=len(arthra),
        plithos_paragrafon=plithos_paragrafon,
        checksum_pigis=apotelesma.checksum,
        checksum_keimenou=hashlib.sha256(keimeno.encode("utf-8")).hexdigest(),
        epalithevmeno_fek=epalithevmeno,
        proeidopoiiseis=proeidopoiiseis,
    )
