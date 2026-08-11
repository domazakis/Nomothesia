"""Έλεγχοι παραγωγής αρχείων corpus, από το δείγμα ΦΕΚ μέχρι τα τελικά αρχεία."""

import json
from pathlib import Path

import pytest

from nomothesia.normalize.emit import (
    grapse_articles_jsonl,
    grapse_full_md,
    grapse_meta_json,
)
from nomothesia.normalize.greek import kanonikopoiise
from nomothesia.normalize.structure import analyse_domi
from nomothesia.registry import fortose_mitroo

FIXTURES = Path(__file__).parent / "fixtures"
PIGI = "https://www.et.gr/api/DownloadFeksApi/?fek_pdf=20250100100"


@pytest.fixture(scope="module")
def arthra():
    keimeno = kanonikopoiise((FIXTURES / "fek_deigma.txt").read_text(encoding="utf-8"))
    return analyse_domi(keimeno)


@pytest.fixture(scope="module")
def nomothetima():
    return fortose_mitroo().get("kok-5209-2025")


def test_full_md_periechei_epikefalida_kai_arthra(tmp_path, nomothetima, arthra):
    diadromi = grapse_full_md(nomothetima, arthra, tmp_path)
    keimeno = diadromi.read_text(encoding="utf-8")

    assert "# Ν. 5209/2025" in keimeno
    assert "Α΄100/13-06-2025" in keimeno
    assert "#### Άρθρο 5 — Σήματα τροχονόμων" in keimeno
    assert "## ΜΕΡΟΣ Α΄" in keimeno
    assert "### ΚΕΦΑΛΑΙΟ Β΄" in keimeno


def test_full_md_proeidopoiei_gia_anepalithefto_fek(tmp_path, nomothetima, arthra):
    # Όσο το ΦΕΚ δεν έχει επαληθευτεί, το αρχείο πρέπει να το λέει καθαρά.
    assert nomothetima.epalithevmeno is False
    keimeno = grapse_full_md(nomothetima, arthra, tmp_path).read_text(encoding="utf-8")
    assert "CAUTION" in keimeno


def test_articles_jsonl_mia_eggrafi_ana_paragrafo(tmp_path, nomothetima, arthra):
    diadromi = grapse_articles_jsonl(nomothetima, arthra, tmp_path, pigi_url=PIGI)
    grammes = diadromi.read_text(encoding="utf-8").strip().split("\n")
    assert len(grammes) == sum(len(a.paragrafoi) for a in arthra)


def test_articles_jsonl_exei_pliri_metadedomena(tmp_path, nomothetima, arthra):
    diadromi = grapse_articles_jsonl(nomothetima, arthra, tmp_path, pigi_url=PIGI)
    eggrafes = [json.loads(gr) for gr in diadromi.read_text(encoding="utf-8").splitlines()]

    stop = next(e for e in eggrafes if "STOP" in e["titlos_arthrou"])
    assert stop["arthro"] == "6"
    assert stop["nomothetima"] == "Ν. 5209/2025"
    assert stop["fek"] == "Α΄100/13-06-2025"
    assert stop["katastasi"] == "isxyon"
    assert stop["pigi_url"] == PIGI
    # Η ταυτότητα πρέπει να επιτρέπει ακριβή παραπομπή σε άρθρο και παράγραφο.
    assert stop["id"].startswith("kok-5209-2025:art-6:par-")


def test_meta_json_katagrafei_proelefsi(tmp_path, nomothetima, arthra):
    diadromi = grapse_meta_json(
        nomothetima, tmp_path, pigi_url=PIGI, checksum_pigis="abc123",
        plithos_arthron=len(arthra), plithos_paragrafon=9,
    )
    meta = json.loads(diadromi.read_text(encoding="utf-8"))
    assert meta["id"] == "kok-5209-2025"
    assert meta["checksum_pigis"] == "abc123"
    assert meta["fek_pdf_id"] == "20250100100"
