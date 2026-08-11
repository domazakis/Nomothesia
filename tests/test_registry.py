"""Έλεγχοι του μητρώου πηγών — τρέχουν πάνω στο πραγματικό registry.yaml."""

import pytest
from pydantic import ValidationError

from nomothesia.registry import (
    Fek,
    Katastasi,
    Mitroo,
    fortose_mitroo,
)


@pytest.fixture(scope="module")
def mitroo() -> Mitroo:
    return fortose_mitroo()


def test_to_pragmatiko_mitroo_einai_egkyro(mitroo):
    assert len(mitroo.nomothetimata) > 0


def test_pdf_id_paragetai_sosta():
    # ΦΕΚ Α΄100/2025 -> έτος 2025, τεύχος Α=01, αριθμός 00100
    fek = Fek(teuxos="A", arithmos=100, imerominia="2025-06-13")
    assert fek.pdf_id == "20250100100"
    assert fek.anafora() == "Α΄100/13-06-2025"


def test_pdf_id_gia_teuxos_deftero():
    fek = Fek(teuxos="B", arithmos=3056, imerominia="2013-12-02")
    assert fek.pdf_id == "20130203056"


def test_agnosto_teuxos_aporriptetai():
    with pytest.raises(ValidationError):
        Fek(teuxos="Ζ", arithmos=1, imerominia="2025-01-01")


def test_o_isxyon_kok_einai_o_5209(mitroo):
    kok = mitroo.get("kok-5209-2025")
    assert kok.katastasi is Katastasi.ISXYON
    assert kok.fek.arithmos == 100


def test_o_palios_kok_den_einai_isxyon(mitroo):
    # Λάθος εδώ σημαίνει ότι ο agent θα απαντούσε με καταργημένο δίκαιο.
    assert mitroo.get("kok-2696-1999").katastasi is not Katastasi.ISXYON


def test_kathe_nomothetima_exei_toulachiston_mia_pigi(mitroo):
    for n in mitroo.nomothetimata:
        assert n.piges, f"{n.id}: χωρίς πηγή"


def test_enosiakes_praxeis_echoun_celex(mitroo):
    for n in mitroo.nomothetimata:
        if n.typos.value in ("kanonismos_ee", "odigia_ee"):
            assert n.celex, f"{n.id}: ενωσιακή πράξη χωρίς CELEX"


def test_ethnika_nomothetimata_echoun_fek(mitroo):
    for n in mitroo.nomothetimata:
        if n.typos.value not in ("kanonismos_ee", "odigia_ee"):
            assert n.fek, f"{n.id}: εθνικό νομοθέτημα χωρίς ΦΕΚ"


def test_oi_scheseis_deichnoun_se_yparkta_nomothetimata(mitroo):
    gnosta = {n.id for n in mitroo.nomothetimata}
    for n in mitroo.nomothetimata:
        for ref in n.scheseis.oles_oi_anafores():
            assert ref in gnosta, f"{n.id} -> άγνωστο {ref}"


def test_diplo_anagnoristiko_aporriptetai():
    dedomena = {
        "meta": {"ekdosi": 1, "enimerosi": "2026-01-01", "perigrafi": "δοκιμή"},
        "nomothetimata": [
            {
                "id": "idio", "titlos": "Α", "typos": "nomos", "arithmos": "1",
                "etos": 2020, "fek": {"teuxos": "A", "arithmos": 1,
                "imerominia": "2020-01-01"}, "thematiki": "kok",
                "proteraiotita": 1, "katastasi": "isxyon", "perigrafi": "δοκιμή",
                "piges": [{"typos": "fek_pdf", "url": "https://example.invalid"}],
            },
        ] * 2,
    }
    with pytest.raises(ValidationError, match="διπλά αναγνωριστικά"):
        Mitroo.model_validate(dedomena)
