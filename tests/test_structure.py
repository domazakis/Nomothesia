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


# ── Τίτλοι που σπάνε σε δεύτερη σειρά ────────────────────────────────────
#
# Στο ΦΕΚ ο τίτλος τυπώνεται κεντραρισμένος και σπάει όπου δεν χωράει. Παίρνοντας
# μόνο την πρώτη σειρά, ο μισός τίτλος κατέληγε στο σώμα ως παράγραφος: στον ΚΟΚ
# του 2025 συνέβαινε σε 22 από τα 132 άρθρα, και το άρθρο για το αλκοόλ φαινόταν
# να λέει «φαρμάκων ή τοξικών ουσιών».


def test_titlos_se_dyo_seires_enonetai():
    keimeno = (
        "Άρθρο 46\n"
        "Οδήγηση υπό την επίδραση οινοπνεύματος,\n"
        "φαρμάκων ή τοξικών ουσιών\n"
        "1. Απαγορεύεται η οδήγηση κάθε οδικού οχήματος.\n"
    )
    (arthro,) = analyse_domi(keimeno)
    assert arthro.titlos == "Οδήγηση υπό την επίδραση οινοπνεύματος, φαρμάκων ή τοξικών ουσιών"
    assert arthro.paragrafoi[0].arithmos == "1"


def test_i_synecheia_tou_titlou_den_ginetai_paragrafos():
    keimeno = "Άρθρο 14\nΕγκατάσταση μέσων σήμανσης\nκαι σηματοδότησης\n1. Η αρχή αποφασίζει.\n"
    (arthro,) = analyse_domi(keimeno)
    assert len(arthro.paragrafoi) == 1
    assert "σηματοδότησης" not in arthro.paragrafoi[0].keimeno


def test_to_enotiko_diloni_synecheia_akoma_kai_me_kefalaio():
    keimeno = (
        "Άρθρο 98\n"
        "Άδειες οδήγησης - Κυρώσεις -\n"
        "Άδειες εκπαιδευτών υποψήφιων οδηγών\n"
        "1. Ισχύουν τα εξής.\n"
    )
    (arthro,) = analyse_domi(keimeno)
    assert arthro.titlos.endswith("Άδειες εκπαιδευτών υποψήφιων οδηγών")


def test_protasi_somatos_den_prosartatai_ston_titlo():
    """Το κεφαλαίο αρχικό προστατεύει το σώμα των άρθρων χωρίς αρίθμηση."""
    keimeno = "Άρθρο 1\nΣκοπός\nΣκοπός του παρόντος είναι η ρύθμιση της κυκλοφορίας.\n"
    (arthro,) = analyse_domi(keimeno)
    assert arthro.titlos == "Σκοπός"
    assert arthro.paragrafoi[0].keimeno.startswith("Σκοπός του παρόντος")


def test_titlos_enotitas_se_dyo_seires_enonetai():
    keimeno = (
        "ΜΕΡΟΣ Β΄\n"
        "ΣΗΜΑΝΣΗ - ΣΗΜΑΤΟΔΟΤΗΣΗ -\n"
        "ΟΔΙΚΗ ΣΥΜΠΕΡΙΦΟΡΑ\n"
        "Άρθρο 6\n"
        "Τροχονόμοι\n"
        "1. Ρυθμίζουν την κυκλοφορία.\n"
    )
    (arthro,) = analyse_domi(keimeno)
    assert arthro.meros.titlos == "ΣΗΜΑΝΣΗ - ΣΗΜΑΤΟΔΟΤΗΣΗ - ΟΔΙΚΗ ΣΥΜΠΕΡΙΦΟΡΑ"
    assert arthro.titlos == "Τροχονόμοι"


# ── Παλιά νομοτεχνική ────────────────────────────────────────────────────
#
# Οι νόμοι της δεκαετίας του '70 και του '80 γράφουν «Άρθρον» και συχνά βάζουν
# τελεία μετά τον αριθμό. Χωρίς αυτό, ο ν. 489/1976 και το π.δ. 237/1986
# κατέβαιναν κανονικά και πετάγονταν ως «κείμενο χωρίς άρθρα».


def test_anagnorizei_to_arthron_ton_palaion_nomon():
    keimeno = (
        "Άρθρον 1\n"
        "Υποχρέωσις ασφαλίσεως\n"
        "1. Ο κύριος του οχήματος υποχρεούται εις ασφάλισιν.\n"
        "Άρθρον 2.\n"
        "Έκτασις ασφαλιστικής καλύψεως\n"
        "1. Η ασφάλισις καλύπτει την έναντι τρίτων ευθύνην.\n"
    )
    arthra = analyse_domi(keimeno)
    assert [a.arithmos for a in arthra] == ["1", "2"]
    assert arthra[1].titlos == "Έκτασις ασφαλιστικής καλύψεως"


def test_i_teleia_meta_ton_arithmo_den_mpainei_ston_arithmo():
    (arthro,) = analyse_domi("Άρθρον 15.\nΤίτλος\n1. Κείμενο.\n")
    assert arthro.arithmos == "15"


def test_parapompi_me_peza_den_theoreitai_epikefalida():
    """«άρθρο 57.» μέσα σε πρόταση δεν είναι αρχή άρθρου.

    Στη διστήλη του ΦΕΚ μια τέτοια παραπομπή πέφτει συχνά στην αρχή γραμμής.
    Στον ΚΟΚ έκοβε το άρθρο 57 στα δύο, με τη μισή διάταξη να γίνεται τίτλος.
    """
    keimeno = (
        "Άρθρο 57\n"
        "Διαστάσεις και βάρη\n"
        "1. Τα οχήματα ακινητοποιούνται σύμφωνα με το\n"
        "άρθρο 57.\n"
        "2. Οι παραβάσεις κατατάσσονται στην κατηγορία γ΄.\n"
    )
    (arthro,) = analyse_domi(keimeno)
    assert arthro.titlos == "Διαστάσεις και βάρη"
    assert len(arthro.paragrafoi) == 2
