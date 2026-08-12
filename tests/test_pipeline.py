"""Έλεγχος ολόκληρου του αγωγού, με προσομοιωμένη λήψη.

Η λήψη αντικαθίσταται από ψεύτικο κατέβασμα που επιστρέφει το αποθηκευμένο
δείγμα ΦΕΚ. Έτσι ο αγωγός δοκιμάζεται από άκρη σε άκρη — λήψη, εξαγωγή,
κανονικοποίηση, δομή, παραγωγή αρχείων — χωρίς να χρειάζεται δίκτυο.
"""

import json
from pathlib import Path

import pytest

from nomothesia.fetch.base import ApotelesmaLipsis, SfalmaLipsis
from nomothesia.pipeline import SfalmaAgogou, epexergasou
from nomothesia.registry import Pigi, TyposPigis, fortose_mitroo

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


class NekriPigi(PsevdiLipsi):
    """Λήψη που αποτυγχάνει για όσα URL περιέχουν ένα δεδομένο κομμάτι.

    Αναπαριστά την πραγματική συνθήκη: το et.gr δεν απαντά, ενώ οι υπόλοιπες
    πηγές δουλεύουν κανονικά.
    """

    def __init__(self, perieksomeno: bytes, nekro: str) -> None:
        super().__init__(perieksomeno)
        self.nekro = nekro

    def kateveste(self, url: str, *, agnoise_cache: bool = False) -> ApotelesmaLipsis:
        self.aitimata.append(url)
        if self.nekro in url:
            raise SfalmaLipsis(f"απέτυχε η λήψη του {url}")
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


def test_agogos_pefti_stin_epomeni_pigi_otan_i_proti_apotygchanei(kok, deigma, tmp_path):
    """Μια νεκρή πηγή δεν πρέπει να αφήνει το νομοθέτημα εκτός corpus.

    Ο ΚΟΚ έχει και κωδικοποιημένη έκδοση· όταν το ΦΕΚ δεν κατεβαίνει, αυτή
    είναι προτιμότερη από το τίποτα.
    """
    lipsi = NekriPigi(deigma, nekro="et.gr")
    apotelesma = epexergasou(kok, lipsi)

    assert len(lipsi.aitimata) == 2
    assert "et.gr" in lipsi.aitimata[0]
    assert (tmp_path / kok.id / "full.md").exists()
    assert apotelesma.plithos_arthron == 4


def test_i_ptosi_sto_topiko_fek_dilonetai_os_idio_eggrafo(kok, deigma):
    """Το τοπικό αντίγραφο είναι το ίδιο ΦΕΚ — δεν πρέπει να μοιάζει υποβάθμιση."""
    apotelesma = epexergasou(kok, NekriPigi(deigma, nekro="et.gr"))
    proeidopoiisi = apotelesma.proeidopoiiseis[0]
    assert "ίδιο έγγραφο" in proeidopoiisi
    assert "sources/fek/" in proeidopoiisi


def test_i_ptosi_se_kodikopoiisi_tritou_dilonetai_os_alli_pigi(kok, deigma):
    """Μια κωδικοποίηση τρίτου είναι άλλο πράγμα και πρέπει να ξεχωρίζει.

    Πέφτουν και το ΦΕΚ και το τοπικό του αντίγραφο· μένει η έκδοση τρίτου.
    """

    class DyoNekres(PsevdiLipsi):
        def kateveste(self, url: str, *, agnoise_cache: bool = False):
            self.aitimata.append(url)
            if "et.gr" in url or url.startswith("file:"):
                raise SfalmaLipsis(f"απέτυχε η λήψη του {url}")
            return ApotelesmaLipsis(
                perieksomeno=self.perieksomeno,
                url=url,
                apo_cache=False,
                typos_perieksomenou="text/html",
            )

    apotelesma = epexergasou(kok, DyoNekres(deigma))
    assert any("προτιμώμενη πηγή απέτυχε" in p for p in apotelesma.proeidopoiiseis)


def test_apotychia_olon_ton_pigon_anaferei_kathe_aitia(kok, deigma):
    lipsi = NekriPigi(deigma, nekro="/")  # κάθε URL έχει «/» — πέφτουν όλες
    with pytest.raises(SfalmaAgogou) as sfalma:
        epexergasou(kok, lipsi)

    minima = str(sfalma.value)
    # Και η επίσημη πηγή και η εναλλακτική πρέπει να αναφέρονται με τον λόγο τους.
    assert "et.gr" in minima
    assert "e-nomothesia.gr" in minima


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



class LipsiAnaUrl(PsevdiLipsi):
    """Λήψη που σερβίρει διαφορετικό περιεχόμενο ανά διεύθυνση."""

    def __init__(self, ana_url: dict[str, bytes]) -> None:
        super().__init__(b"")
        self.ana_url = ana_url

    def kateveste(self, url: str, *, agnoise_cache: bool = False) -> ApotelesmaLipsis:
        self.aitimata.append(url)
        return ApotelesmaLipsis(
            perieksomeno=self.ana_url[url],
            url=url,
            apo_cache=False,
            typos_perieksomenou="text/html",
        )


def test_to_sympliroma_gemizei_mono_ta_kena(kok, deigma, tmp_path):
    """Το συμπλήρωμα προσθέτει όσα άρθρα λείπουν — δεν ξαναγράφει όσα υπάρχουν.

    Η κύρια πηγή μένει η καλύτερη για ό,τι έχει· το συμπλήρωμα υπάρχει επειδή
    καμία πηγή του π.δ. 237/1986 δεν δίνει και τα πενήντα οκτώ άρθρα του.
    """
    kok.piges = [
        Pigi(typos=TyposPigis.FEK_PDF, url="https://et.gr/fek"),
        Pigi(typos=TyposPigis.SYMPLIROMA, url="https://opou/sympliroma.txt"),
    ]
    lipsi = LipsiAnaUrl(
        {
            "https://et.gr/fek": deigma,
            "https://opou/sympliroma.txt": (
                "Άρθρο 5\nΑπό το συμπλήρωμα, όχι από το ΦΕΚ.\n\n"
                "Άρθρο 99\nΤελικές διατάξεις\n1. Το τελευταίο άρθρο.\n"
            ).encode(),
        }
    )

    apotelesma = epexergasou(kok, lipsi)

    grammes = [
        json.loads(gr)
        for gr in (tmp_path / kok.id / "articles.jsonl").read_text().splitlines()
    ]
    arithmoi = sorted({g["arthro"] for g in grammes}, key=int)
    assert arithmoi == ["1", "5", "6", "99", "132"]
    # Το άρθρο 5 υπήρχε ήδη στο ΦΕΚ και δεν αντικαταστάθηκε.
    keimeno_5 = " ".join(g["keimeno"] for g in grammes if g["arthro"] == "5")
    assert "Από το συμπλήρωμα" not in keimeno_5
    assert any("συμπλήρωμα" in p for p in apotelesma.proeidopoiiseis)
