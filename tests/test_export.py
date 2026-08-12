"""Έλεγχοι του knowledge base που τροφοδοτεί τον φωνητικό agent."""

from __future__ import annotations

import json

import pytest

from nomothesia import export as ex
from nomothesia.registry import Katastasi, fortose_mitroo


def _grapse_arthra(fakelos, eggrafes):
    fakelos.mkdir(parents=True, exist_ok=True)
    (fakelos / "articles.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in eggrafes) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def kok(monkeypatch, tmp_path):
    n = fortose_mitroo().get("kok-5209-2025")
    monkeypatch.setattr(type(n), "fakelos_corpus", lambda self: tmp_path / self.id)
    monkeypatch.setattr(ex, "fakelos_export", lambda: tmp_path / "export")
    return n


@pytest.fixture
def keimeno(kok, tmp_path):
    _grapse_arthra(
        kok.fakelos_corpus(),
        [
            {
                "arthro": "46",
                "titlos_arthrou": "Οδήγηση υπό την επίδραση οινοπνεύματος",
                "meros_titlos": "ΟΔΙΚΗ ΣΥΜΠΕΡΙΦΟΡΑ",
                "kefalaio_titlos": "",
                "paragrafos": "1",
                "keimeno": "Κατά την παρ. 2 του π.δ. 237/1986 ισχύει το όριο.",
            }
        ],
    )
    apotelesma = ex.exagoge_nomothetimatos(kok)
    return apotelesma.diadromi.read_text(encoding="utf-8")


def test_kathe_arthro_kouvala_tin_tautotita_tou(keimeno):
    """Όπου κι αν πέσει η τομή του chunker, η παραπομπή ταξιδεύει μαζί."""
    assert "Άρθρο 46" in keimeno
    assert "Νόμος 5209 του 2025" in keimeno
    assert "ΦΕΚ τεύχος Άλφα, αριθμός 100" in keimeno


def test_i_imerominia_grafetai_ologrofos(keimeno):
    assert "13 Ιουνίου 2025" in keimeno
    assert "2025-06-13" not in keimeno


def test_oi_syntomografies_anoigoun_sto_export(keimeno):
    assert "παράγραφος 2 του προεδρικού διατάγματος 237 του 1986" in keimeno
    assert "παρ." not in keimeno
    assert "π.δ." not in keimeno


def test_i_paragrafos_arithmeitai_anagnosima(keimeno):
    assert "Παράγραφος 1." in keimeno


# ── Τι δεν φτάνει ποτέ στη φωνή ──────────────────────────────────────────


def test_ta_katargimena_menoun_ektos():
    """Ένας agent που απαντά με καταργημένη διάταξη δίνει λάθος απάντηση."""
    mitroo = fortose_mitroo()
    epilegmena = ex.gia_knowledge_base(mitroo)

    assert all(n.katastasi is Katastasi.ISXYON for n in epilegmena)
    assert "kok-2696-1999" not in {n.id for n in epilegmena}
    assert "kok-5209-2025" in {n.id for n in epilegmena}


def test_nomothetima_ektos_corpus_den_paragei_arxeio(kok):
    assert ex.exagoge_nomothetimatos(kok) is None


def test_idios_arithmos_arthrou_se_dyo_meri_den_synchoneuetai(kok):
    """Ο ίδιος αριθμός επανεμφανίζεται σε άλλο Μέρος — είναι άλλο άρθρο."""
    _grapse_arthra(
        kok.fakelos_corpus(),
        [
            {"arthro": "1", "titlos_arthrou": "Σκοπός", "meros_titlos": "Α",
             "kefalaio_titlos": "", "paragrafos": "1", "keimeno": "Πρώτο."},
            {"arthro": "2", "titlos_arthrou": "Ορισμοί", "meros_titlos": "Α",
             "kefalaio_titlos": "", "paragrafos": "1", "keimeno": "Δεύτερο."},
            {"arthro": "1", "titlos_arthrou": "Πεδίο", "meros_titlos": "Β",
             "kefalaio_titlos": "", "paragrafos": "1", "keimeno": "Τρίτο."},
        ],
    )
    apotelesma = ex.exagoge_nomothetimatos(kok)
    assert apotelesma.plithos_arthron == 3


def test_oi_simeioseis_taxidevoun_me_to_knowledge_base(kok, tmp_path):
    """Ό,τι προειδοποιεί για την πηγή πρέπει να φτάνει στον πράκτορα.

    Τα άρθρα 11-24 του π.δ. 237/1986 φέρουν τη διατύπωση του 1986, με
    πρόστιμα σε δραχμές. Αν η προειδοποίηση μείνει στο μητρώο, ο πράκτορας
    τα απαγγέλλει σαν να ισχύουν.
    """
    kok.prosochi = "Τα άρθρα 11-24 φέρουν τη διατύπωση του 1986."
    _grapse_arthra(
        kok.fakelos_corpus(),
        [{"arthro": "1", "paragrafos": "1", "keimeno": "Κείμενο."}],
    )

    keimeno = ex.exagoge_nomothetimatos(kok).diadromi.read_text(encoding="utf-8")

    assert "Προσοχή" in keimeno
    assert "φέρουν τη διατύπωση του 1986" in keimeno
