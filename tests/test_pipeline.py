"""Έλεγχος ολόκληρου του αγωγού, με προσομοιωμένη λήψη.

Η λήψη αντικαθίσταται από ψεύτικο κατέβασμα που επιστρέφει το αποθηκευμένο
δείγμα ΦΕΚ. Έτσι ο αγωγός δοκιμάζεται από άκρη σε άκρη — λήψη, εξαγωγή,
κανονικοποίηση, δομή, παραγωγή αρχείων — χωρίς να χρειάζεται δίκτυο.
"""

import json
from pathlib import Path

import pytest

from nomothesia.fetch.base import ApotelesmaLipsis
from nomothesia.pipeline import SfalmaAgogou, epexergasou
from nomothesia.registry import fortose_mitroo

FIXTURES = Path(__file__).parent / "fixtures"


class PsevdiLipsi:
    """Υποκατάστατο του `Lipsi` που σερβίρει σταθερό περιεχόμενο."""

    def __init__(self, perieksomeno: bytes) -> None:
        self.perieksomeno = perieksomeno
        self.aitimata: list[str] = []

    def kateveste(self, url: str, *, agnoise_cache: bool = False) -> ApotelesmaLipsis:
        self.aitimata.append(url)
        return ApotelesmaLipsis(
            perieksomeno=self.perieksomeno,
            url=url,
            apo_cache=False,
            typos_perieksomenou="text/html",
        )


@pytest.fixture
def kok(monkeypatch, tmp_path):
    """Το νομοθέτημα του ΚΟΚ, με το corpus του να γράφεται σε προσωρινό φάκελο."""
    n = fortose_mitroo().get("kok-5209-2025")
    monkeypatch.setattr(type(n), "fakelos_corpus", lambda self: tmp_path / self.id)
    return n


@pytest.fixture
def deigma() -> bytes:
    return (FIXTURES / "fek_deigma.txt").read_bytes()


def test_agogos_paragei_kai_ta_tria_arxeia(kok, deigma, tmp_path):
    apotelesma = epexergasou(kok, PsevdiLipsi(deigma))

    fakelos = tmp_path / kok.id
    assert (fakelos / "full.md").exists()
    assert (fakelos / "articles.jsonl").exists()
    assert (fakelos / "meta.json").exists()
    assert apotelesma.plithos_arthron == 4


def test_agogos_epalithevei_ta_stoicheia_fek(kok, deigma):
    # Το δείγμα περιέχει «Τεύχος Α΄100/13.06.2025», άρα η επαλήθευση πετυχαίνει.
    apotelesma = epexergasou(kok, PsevdiLipsi(deigma))
    assert apotelesma.epalithevmeno_fek is True
    assert apotelesma.proeidopoiiseis == []


def test_agogos_proeidopoiei_otan_to_fek_den_taitiazei(kok):
    alo_fek = b"Kappa\n\xce\x86\xcf\x81\xce\xb8\xcf\x81\xce\xbf 1\n\n1. Kati allo.\n"
    apotelesma = epexergasou(kok, PsevdiLipsi(alo_fek))
    assert apotelesma.epalithevmeno_fek is False
    assert any("ΦΕΚ" in p for p in apotelesma.proeidopoiiseis)


def test_agogos_apotygchanei_katharo_otan_den_yparchoun_arthra(kok):
    keimeno_xoris_domi = "Απλό κείμενο χωρίς άρθρα.".encode()
    with pytest.raises(SfalmaAgogou, match="δεν εντοπίστηκε κανένα άρθρο"):
        epexergasou(kok, PsevdiLipsi(keimeno_xoris_domi))


def test_agogos_apotygchanei_se_keno_keimeno(kok):
    with pytest.raises(SfalmaAgogou):
        epexergasou(kok, PsevdiLipsi(b"   \n  \n"))


def test_agogos_protima_tin_pigi_fek(kok, deigma):
    # Ο ΚΟΚ έχει και κωδικοποιημένη πηγή· πρέπει να προτιμηθεί το επίσημο ΦΕΚ.
    lipsi = PsevdiLipsi(deigma)
    epexergasou(kok, lipsi)
    assert "et.gr" in lipsi.aitimata[0]


def test_paragomeno_jsonl_einai_egkyro(kok, deigma, tmp_path):
    epexergasou(kok, PsevdiLipsi(deigma))
    grammes = (tmp_path / kok.id / "articles.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    eggrafes = [json.loads(gr) for gr in grammes]

    assert all(e["nomothetima_id"] == "kok-5209-2025" for e in eggrafes)
    assert all(e["keimeno"].strip() for e in eggrafes)
    # Οι ταυτότητες πρέπει να είναι μοναδικές, αλλιώς η ανάκτηση θα διπλογράφει.
    anagnoristika = [e["id"] for e in eggrafes]
    assert len(anagnoristika) == len(set(anagnoristika))


def test_epalithefsi_ftanei_se_ola_ta_arxeia(kok, deigma, tmp_path):
    """Η επαλήθευση του ΦΕΚ γίνεται στον αγωγό — δεν πρέπει να χαθεί στα αρχεία.

    Το μητρώο δηλώνει `epalithevmeno: false` ως αφετηρία· όταν ο αγωγός
    επιβεβαιώσει το ΦΕΚ, τα παραγόμενα αρχεία πρέπει να το αντικατοπτρίζουν.
    """
    assert kok.epalithevmeno is False
    epexergasou(kok, PsevdiLipsi(deigma))
    fakelos = tmp_path / kok.id

    assert "CAUTION" not in (fakelos / "full.md").read_text(encoding="utf-8")
    assert json.loads((fakelos / "meta.json").read_text(encoding="utf-8"))["epalithevmeno"]
    eggrafi = json.loads((fakelos / "articles.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert eggrafi["epalithevmeno"] is True


def test_keimeno_paragrafou_den_exei_alages_grammis(kok, deigma, tmp_path):
    epexergasou(kok, PsevdiLipsi(deigma))
    grammes = (tmp_path / kok.id / "articles.jsonl").read_text(encoding="utf-8").splitlines()
    for gr in grammes:
        assert "\n" not in json.loads(gr)["keimeno"]
