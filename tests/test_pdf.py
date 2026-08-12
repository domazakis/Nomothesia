"""Έλεγχοι ανίχνευσης διστήλης διάταξης.

Η ανίχνευση είναι το πιο εύθραυστο σημείο της εξαγωγής: αν αποτύχει, το κείμενο
βγαίνει ανακατεμένο ανάμεσα στις δύο στήλες και το λάθος δεν είναι εμφανές με
γυμνό μάτι. Ελέγχεται εδώ με συνθετικές σελίδες αντί για πραγματικό PDF, ώστε
τα tests να τρέχουν χωρίς δίκτυο και χωρίς βαριά δείγματα.
"""

from dataclasses import dataclass

import pytest

from nomothesia.extract.pdf import _avlaki

PLATOS = 600.0


@dataclass
class PsevdoSelida:
    """Ελάχιστο υποκατάστατο σελίδας pdfplumber: πλάτος και θέσεις λέξεων."""

    lexeis: list[dict]
    width: float = PLATOS
    height: float = 800.0

    def extract_words(self):
        return self.lexeis


def _lexeis_se_stili(x0: float, x1: float, plithos: int) -> list[dict]:
    return [{"x0": x0, "x1": x1} for _ in range(plithos)]


def test_distili_selida_anagnorizetai():
    # Δύο στήλες: 0-280 και 320-600. Καμία λέξη δεν πατά στο κέντρο (300).
    lexeis = _lexeis_se_stili(20, 270, 40) + _lexeis_se_stili(330, 580, 40)
    assert _avlaki(PsevdoSelida(lexeis)) is not None


def test_monostili_selida_den_anagnorizetai_os_distili():
    # Λέξεις που διασχίζουν όλο το πλάτος, άρα και το κέντρο.
    lexeis = _lexeis_se_stili(20, 580, 80)
    assert _avlaki(PsevdoSelida(lexeis)) is None


def test_selida_me_ligo_keimeno_den_theoreitai_distili():
    # Εξώφυλλο ή σελίδα με τίτλο μόνο: πολύ λίγα δεδομένα για ασφαλή κρίση.
    lexeis = _lexeis_se_stili(20, 270, 5)
    assert _avlaki(PsevdoSelida(lexeis)) is None


def test_keni_selida_den_theoreitai_distili():
    assert _avlaki(PsevdoSelida([])) is None


# ── Αυλάκι εκτός κέντρου ─────────────────────────────────────────────────
#
# Το ΦΕΚ Α΄82/2012 έχει το αυλάκι στο 53% του πλάτους. Με την παραδοχή ότι
# βρίσκεται πάντα στο μέσο, η σελίδα κρινόταν μονόστηλη και οι δύο στήλες
# διαβάζονταν πλεγμένες: από 740 χιλιάδες χαρακτήρες έβγαιναν 15 άρθρα αντί
# για 196.


def test_vriskei_avlaki_ektos_kentrou():
    aristeri = _lexeis_se_stili(40, PLATOS * 0.50, 120)
    dexia = _lexeis_se_stili(PLATOS * 0.56, PLATOS - 40, 120)
    avlaki = _avlaki(PsevdoSelida(aristeri + dexia))

    assert avlaki is not None
    assert PLATOS * 0.50 <= avlaki <= PLATOS * 0.56


def test_i_tomi_pefti_sto_kentro_tou_avlakiou():
    """Σε φαρδύ αυλάκι πολλές θέσεις ισοβαθμούν· η τομή πάει στη μέση τους."""
    aristeri = _lexeis_se_stili(40, PLATOS * 0.42, 120)
    dexia = _lexeis_se_stili(PLATOS * 0.58, PLATOS - 40, 120)
    avlaki = _avlaki(PsevdoSelida(aristeri + dexia))

    assert avlaki == pytest.approx(PLATOS * 0.50, abs=PLATOS * 0.03)


def test_kefalida_pou_diaschizei_den_akyroni_tin_anichnefsi():
    """Η κεφαλίδα σελίδας διασχίζει κάθε θέση· δεν πρέπει να κρύψει το αυλάκι."""
    aristeri = _lexeis_se_stili(40, PLATOS * 0.48, 200)
    dexia = _lexeis_se_stili(PLATOS * 0.52, PLATOS - 40, 200)
    kefalida = _lexeis_se_stili(40, PLATOS - 40, 3)

    assert _avlaki(PsevdoSelida(aristeri + dexia + kefalida)) is not None
