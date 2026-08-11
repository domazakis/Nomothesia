"""Ο αγωγός: λήψη → εξαγωγή → κανονικοποίηση → δομή → αρχεία corpus."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

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
PROTERAIOTITA_EX_ORISMOU = (
    TyposPigis.FEK_PDF,
    TyposPigis.KODIKOPOIIMENO_HTML,
    TyposPigis.PDF_ALLI_PIGI,
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


def _epilexe_pigi(n: Nomothetima):
    seira = PROTERAIOTITA_PIGON.get(n.typos, PROTERAIOTITA_EX_ORISMOU)
    for typos in seira:
        for pigi in n.piges:
            if pigi.typos is typos:
                return pigi
    if n.piges:
        return n.piges[0]
    raise SfalmaAgogou(f"{n.id}: καμία διαθέσιμη πηγή")


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
    """Τρέχει ολόκληρο τον αγωγό για ένα νομοθέτημα και γράφει τα αρχεία του."""
    proeidopoiiseis: list[str] = []
    pigi = _epilexe_pigi(n)

    try:
        apotelesma = lipsi.kateveste(pigi.url, agnoise_cache=agnoise_cache)
    except SfalmaLipsis as exc:
        raise SfalmaAgogou(f"{n.id}: {exc}") from exc

    if apotelesma.einai_pdf:
        if not exei_epipedo_keimenou(apotelesma.perieksomeno):
            raise SfalmaAgogou(
                f"{n.id}: το PDF δεν έχει επίπεδο κειμένου (σαρωμένο). "
                f"Χρειάζεται OCR — εγκατάσταση με `pip install 'nomothesia[ocr]'`."
            )
        akatergasto = keimeno_apo_pdf(apotelesma.perieksomeno)
    else:
        akatergasto = keimeno_apo_html(apotelesma.perieksomeno)

    keimeno = kanonikopoiise(akatergasto)
    if not keimeno.strip():
        raise SfalmaAgogou(f"{n.id}: δεν εξήχθη καθόλου κείμενο από {pigi.url}")

    epalithevmeno = _epalithefse_fek(n, akatergasto)
    if n.fek and not epalithevmeno:
        proeidopoiiseis.append(
            "τα στοιχεία ΦΕΚ δεν εντοπίστηκαν στην αρχή του κειμένου — "
            "ελέγξτε το pdf_id στο registry.yaml"
        )

    arthra = _filtrare_arthra(n, analyse_domi(keimeno))
    if not arthra:
        raise SfalmaAgogou(
            f"{n.id}: δεν εντοπίστηκε κανένα άρθρο. Πιθανή αιτία: αλλαγή "
            f"διάταξης στην πηγή ή λάθος URL."
        )

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
