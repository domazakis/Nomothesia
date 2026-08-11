"""Έλεγχοι ανίχνευσης διστήλης διάταξης.

Η ανίχνευση είναι το πιο εύθραυστο σημείο της εξαγωγής: αν αποτύχει, το κείμενο
βγαίνει ανακατεμένο ανάμεσα στις δύο στήλες και το λάθος δεν είναι εμφανές με
γυμνό μάτι. Ελέγχεται εδώ με συνθετικές σελίδες αντί για πραγματικό PDF, ώστε
τα tests να τρέχουν χωρίς δίκτυο και χωρίς βαριά δείγματα.
"""

from dataclasses import dataclass

from nomothesia.extract.pdf import _einai_distili

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
    assert _einai_distili(PsevdoSelida(lexeis)) is True


def test_monostili_selida_den_anagnorizetai_os_distili():
    # Λέξεις που διασχίζουν όλο το πλάτος, άρα και το κέντρο.
    lexeis = _lexeis_se_stili(20, 580, 80)
    assert _einai_distili(PsevdoSelida(lexeis)) is False


def test_selida_me_ligo_keimeno_den_theoreitai_distili():
    # Εξώφυλλο ή σελίδα με τίτλο μόνο: πολύ λίγα δεδομένα για ασφαλή κρίση.
    lexeis = _lexeis_se_stili(20, 270, 5)
    assert _einai_distili(PsevdoSelida(lexeis)) is False


def test_keni_selida_den_theoreitai_distili():
    assert _einai_distili(PsevdoSelida([])) is False
