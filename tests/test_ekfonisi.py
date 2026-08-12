"""Έλεγχοι της μετατροπής σε μορφή εκφώνησης."""

from __future__ import annotations

import pytest

from nomothesia.normalize.ekfonisi import gia_ekfonisi


@pytest.mark.parametrize(
    ("grafto", "eipomeno"),
    [
        ("παρ. 2", "παράγραφος 2"),
        ("περ. β΄", "περίπτωση βήτα"),
        ("υποπερ. αα΄", "υποπερίπτωση αα΄"),
        ("εδ. 3", "εδάφιο 3"),
        ("του π.δ. 237/1986", "του προεδρικού διατάγματος 237 του 1986"),
        ("του ν. 2696/1999", "του νόμου 2696 του 1999"),
        ("της κ.υ.α. 12345", "της κοινής υπουργικής απόφασης 12345"),
        ("ταχύτητα 50 χλμ/ώρα", "ταχύτητα 50 χιλιόμετρα την ώρα"),
        ("0,50 γρ./λίτρο", "0,50 γραμμάρια ανά λίτρο"),
        ("ποινή 20%", "ποινή 20 τοις εκατό"),
        ("πρόστιμο 200€", "πρόστιμο 200 ευρώ"),
        ("οχήματα κ.λπ.", "οχήματα και λοιπά"),
    ],
)
def test_anoigei_tis_syntomografies(grafto, eipomeno):
    assert gia_ekfonisi(grafto) == eipomeno


def test_ta_eidi_nomothetimaton_grafontai_se_geniki():
    """Οι παραπομπές στα ΦΕΚ είναι σχεδόν πάντα σε γενική: «του ν.», «της κ.υ.α.».

    Η γενική είναι λοιπόν η σωστή προεπιλογή. Σε ονομαστική η φράση βγαίνει
    αδέξια, αλλά η περίπτωση είναι σπάνια και προτιμότερη από το να μαντεύει ο
    κώδικας πτώσεις μέσα σε νομικό κείμενο.
    """
    assert gia_ekfonisi("κατά το άρθρο 2 του ν. 4530/2018") == (
        "κατά το άρθρο 2 του νόμου 4530 του 2018"
    )


def test_meros_kai_kefalaio_ginontai_anagnosima():
    assert gia_ekfonisi("ΜΕΡΟΣ Β΄") == "ΜΕΡΟΣ Βήτα"
    assert gia_ekfonisi("Κεφάλαιο Α΄") == "Κεφάλαιο Άλφα"


# ── Τι δεν πρέπει να πειραχτεί ───────────────────────────────────────────
#
# Το κείμενο είναι νομοθεσία. Μια λάθος «διόρθωση» είναι χειρότερη από μια
# συντομογραφία που ακούγεται άσχημα, οπότε οι κανόνες θέλουν συμφραζόμενα.


def test_to_ni_choris_arithmo_den_ginetai_nomos():
    """Χωρίς αριθμό δεν πρόκειται για παραπομπή σε νόμο."""
    assert gia_ekfonisi("την ν. εταιρεία") == "την ν. εταιρεία"


def test_lexi_pou_teleionei_se_syntomografia_den_allazei():
    assert "παράγραφος" not in gia_ekfonisi("υπεράσπιση")
    assert gia_ekfonisi("Καθαρ. 5") == "Καθαρ. 5"


def test_klasma_den_ginetai_arithmos_nomothetimatos():
    """Το «του» μπαίνει μόνο όταν το δεύτερο σκέλος μοιάζει με έτος."""
    assert gia_ekfonisi("αναλογία 3/4") == "αναλογία 3/4"
    assert gia_ekfonisi("άρθρο 5/2026") == "άρθρο 5 του 2026"


def test_imerominia_den_paramorfonetai():
    assert gia_ekfonisi("13-6-2025") == "13-6-2025"


def test_keimeno_choris_syntomografies_menei_idio():
    keimeno = "Απαγορεύεται η οδήγηση υπό την επίδραση οινοπνεύματος."
    assert gia_ekfonisi(keimeno) == keimeno
