"""Έλεγχοι ανάλυσης δομής νομοθετήματος πάνω σε δείγμα ΦΕΚ."""

from pathlib import Path

import pytest

from nomothesia.normalize.greek import kanonikopoiise
from nomothesia.normalize.structure import analyse_domi

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def arthra():
    akatergasto = (FIXTURES / "fek_deigma.txt").read_text(encoding="utf-8")
    return analyse_domi(kanonikopoiise(akatergasto))


def test_vriskei_ola_ta_arthra(arthra):
    assert [a.arithmos for a in arthra] == ["1", "5", "6", "132"]


def test_apodidei_titlous_arthron(arthra):
    titloi = {a.arithmos: a.titlos for a in arthra}
    assert titloi["5"] == "Σήματα τροχονόμων"
    assert titloi["6"] == "Πινακίδα STOP"
    assert titloi["132"] == "Έναρξη ισχύος"


def test_apodidei_meros_kai_kefalaio(arthra):
    kata_arithmo = {a.arithmos: a for a in arthra}
    assert kata_arithmo["1"].meros.arithmisi == "Α"
    assert kata_arithmo["1"].kefalaio.arithmisi == "Α"
    # Το άρθρο 5 βρίσκεται στο ίδιο Μέρος αλλά σε επόμενο Κεφάλαιο.
    assert kata_arithmo["5"].meros.arithmisi == "Α"
    assert kata_arithmo["5"].kefalaio.arithmisi == "Β"
    # Το άρθρο 132 έχει περάσει σε νέο Μέρος.
    assert kata_arithmo["132"].meros.arithmisi == "Β"


def test_apodidei_titlous_enotiton(arthra):
    kata_arithmo = {a.arithmos: a for a in arthra}
    assert kata_arithmo["1"].meros.titlos == "ΓΕΝΙΚΕΣ ΔΙΑΤΑΞΕΙΣ"
    assert kata_arithmo["1"].kefalaio.titlos == "ΣΚΟΠΟΣ ΚΑΙ ΑΝΤΙΚΕΙΜΕΝΟ"
    assert kata_arithmo["5"].kefalaio.titlos == "ΚΑΝΟΝΕΣ ΚΥΚΛΟΦΟΡΙΑΣ ΟΧΗΜΑΤΩΝ"
    assert kata_arithmo["132"].meros.titlos == "ΚΥΡΩΣΕΙΣ"


def test_epikefalides_den_diarreoun_stin_teleftaia_paragrafo(arthra):
    """Το σώμα ενός άρθρου σταματά στον επόμενο δομικό δείκτη, όχι στο επόμενο άρθρο.

    Χωρίς αυτό, το «ΚΕΦΑΛΑΙΟ Β΄ / ΚΑΝΟΝΕΣ ΚΥΚΛΟΦΟΡΙΑΣ» κατέληγε κολλημένο στο
    τέλος της παρ. 2 του άρθρου 1.
    """
    for a in arthra:
        for p in a.paragrafoi:
            assert "ΚΕΦΑΛΑΙΟ" not in p.keimeno
            assert "ΜΕΡΟΣ" not in p.keimeno


def test_neo_meros_midenizei_ta_kefalaia(arthra):
    # Το άρθρο 132 ανήκει στο ΜΕΡΟΣ Β΄, που δεν έχει δικό του Κεφάλαιο στο δείγμα.
    assert next(a for a in arthra if a.arithmos == "132").kefalaio is None


def test_spaei_se_paragrafous(arthra):
    arthro_5 = next(a for a in arthra if a.arithmos == "5")
    assert [p.arithmos for p in arthro_5.paragrafoi] == ["1", "2"]


def test_krata_keimeno_prin_tin_proti_paragrafo(arthra):
    # Το άρθρο 1 έχει εισαγωγική πρόταση πριν από την «1.» — δεν πρέπει να χαθεί.
    arthro_1 = next(a for a in arthra if a.arithmos == "1")
    assert arthro_1.paragrafoi[0].arithmos == ""
    assert "ενίσχυση της οδικής ασφάλειας" in arthro_1.paragrafoi[0].keimeno


def test_syllavismos_enonetai_mesa_stin_paragrafo(arthra):
    arthro_5 = next(a for a in arthra if a.arithmos == "5")
    assert "κυκλοφορία" in arthro_5.paragrafoi[0].keimeno
    assert "κυκλοφο-" not in arthro_5.paragrafoi[0].keimeno


def test_thoryvos_selidas_den_mpainei_sto_keimeno(arthra):
    for a in arthra:
        for p in a.paragrafoi:
            assert "ΕΦΗΜΕΡΙΔΑ" not in p.keimeno
            assert "ΚΥΒΕΡΝΗΣΕΩΣ" not in p.keimeno


def test_keimeno_xoris_arthra_epistrefei_kena():
    assert analyse_domi("Απλό κείμενο χωρίς καμία δομή άρθρων.") == []
