"""Έλεγχοι ανίχνευσης αλλαγών — το κύριο πρόβλημα που λύνει το project."""

from nomothesia.changes import (
    EidosAllagis,
    fortose_manifest,
    grapse_manifest,
    ousiastikes,
    sygkrine,
)


def test_neo_nomothetima_anagnorizetai():
    allages = sygkrine({}, {"kok-5209-2025": {"checksum_keimenou": "a"}})
    assert allages[0].eidos is EidosAllagis.NEO


def test_tropopoiisi_anagnorizetai():
    palio = {"kok-5209-2025": {"checksum_keimenou": "a"}}
    neo = {"kok-5209-2025": {"checksum_keimenou": "b"}}
    assert sygkrine(palio, neo)[0].eidos is EidosAllagis.TROPOPOIIMENO


def test_ametavlito_anagnorizetai():
    idio = {"kok-5209-2025": {"checksum_keimenou": "a"}}
    assert sygkrine(idio, idio)[0].eidos is EidosAllagis.ACHANGE


def test_afairemeno_nomothetima_anagnorizetai():
    allages = sygkrine({"palio": {"checksum_keimenou": "a"}}, {})
    assert allages[0].eidos is EidosAllagis.APON


def test_ousiastikes_apokleioun_ta_ametavlita():
    palio = {"a": {"checksum_keimenou": "1"}, "b": {"checksum_keimenou": "2"}}
    neo = {"a": {"checksum_keimenou": "1"}, "b": {"checksum_keimenou": "ΑΛΛΑΞΕ"}}
    ousiastika = ousiastikes(sygkrine(palio, neo))
    assert [a.nomothetima_id for a in ousiastika] == ["b"]


def test_manifest_grafetai_kai_diavazetai(tmp_path):
    diadromi = tmp_path / "MANIFEST.json"
    eggrafes = {"kok-5209-2025": {"checksum_keimenou": "abc", "plithos_arthron": 132}}
    grapse_manifest(eggrafes, diadromi)
    assert fortose_manifest(diadromi) == eggrafes


def test_manifest_pou_leipei_epistrefei_keno(tmp_path):
    assert fortose_manifest(tmp_path / "den-yparchei.json") == {}
