"""Εξαγωγή κειμένου από ΦΕΚ σε μορφή PDF.

Το κρίσιμο σημείο είναι η **διστήλη διάταξη**. Τα ΦΕΚ τυπώνονται σε δύο στήλες
ανά σελίδα. Οι συνηθισμένες βιβλιοθήκες διαβάζουν από πάνω προς τα κάτω και από
αριστερά προς τα δεξιά, οπότε πλέκουν τις δύο στήλες μεταξύ τους και παράγουν
κείμενο που μοιάζει σωστό αλλά είναι ανακατεμένο πρόταση παρά πρόταση.

Γι' αυτό ανιχνεύουμε τη διάταξη και, όταν πρόκειται για δύο στήλες, κόβουμε τη
σελίδα στη μέση και διαβάζουμε κάθε στήλη χωριστά.
"""

from __future__ import annotations

import io
import logging

import pdfplumber

logger = logging.getLogger(__name__)

# Κάτω από τόσες λέξεις, η ανίχνευση στηλών δεν είναι αξιόπιστη.
ELAXISTES_LEXEIS = 40
# Ανεκτικότητα σε λέξεις που όντως διασχίζουν το κέντρο (τίτλοι σε όλο το
# πλάτος, υποσημειώσεις). Πάνω από αυτό το ποσοστό, η σελίδα είναι μονόστηλη.
ANEKTIKOTITA_DIASCHISIS = 0.02


def _einai_distili(selida) -> bool:
    """Αληθές όταν η σελίδα έχει καθαρό κατακόρυφο αυλάκι στο κέντρο.

    Μετράμε πόσες λέξεις διασχίζουν την κεντρική κατακόρυφο. Σε μονόστηλη
    σελίδα τη διασχίζουν συνεχώς· σε διστήλη, σχεδόν καμία.

    Προϋποθέτει συμμετρικά περιθώρια, όπως έχουν τα ΦΕΚ. Σε σελίδα με έντονα
    ασύμμετρες στήλες η κεντρική κατακόρυφος θα έπεφτε μέσα σε στήλη και η
    σελίδα θα αντιμετωπιστεί ως μονόστηλη — συντηρητικό και ασφαλές σφάλμα,
    αφού η μονόστηλη ανάγνωση δεν χάνει κείμενο, απλώς μπορεί να το ανακατέψει.
    """
    lexeis = selida.extract_words() or []
    if len(lexeis) < ELAXISTES_LEXEIS:
        return False

    kentro = float(selida.width) / 2
    diaschizoun = sum(
        1 for w in lexeis if float(w["x0"]) < kentro < float(w["x1"])
    )
    return diaschizoun / len(lexeis) < ANEKTIKOTITA_DIASCHISIS


def _keimeno_stilis(selida, x0: float, x1: float) -> str:
    perioxi = selida.crop((x0, 0, x1, selida.height))
    return perioxi.extract_text() or ""


def keimeno_apo_pdf(dedomena: bytes) -> str:
    """Επιστρέφει το κείμενο ολόκληρου του PDF, σεβόμενο τις στήλες.

    Δεν κάνει κανονικοποίηση — αυτή είναι δουλειά του `normalize.greek`.
    """
    kommatia: list[str] = []

    with pdfplumber.open(io.BytesIO(dedomena)) as pdf:
        for arithmos, selida in enumerate(pdf.pages, start=1):
            try:
                if _einai_distili(selida):
                    kentro = float(selida.width) / 2
                    kommatia.append(_keimeno_stilis(selida, 0, kentro))
                    kommatia.append(_keimeno_stilis(selida, kentro, float(selida.width)))
                else:
                    kommatia.append(selida.extract_text() or "")
            except Exception as exc:  # μία κακή σελίδα δεν ακυρώνει το ΦΕΚ
                logger.warning("σελίδα %d: αποτυχία εξαγωγής (%s)", arithmos, exc)

    return "\n".join(kommatia)


def exei_epipedo_keimenou(dedomena: bytes, *, elegxomenes_selides: int = 3) -> bool:
    """Ελέγχει αν το PDF έχει ενσωματωμένο κείμενο ή είναι σαρωμένη εικόνα.

    Αν επιστρέψει False, το αρχείο χρειάζεται OCR και δεν μπορεί να μπει στο
    corpus ως έχει.
    """
    with pdfplumber.open(io.BytesIO(dedomena)) as pdf:
        for selida in pdf.pages[:elegxomenes_selides]:
            if (selida.extract_text() or "").strip():
                return True
    return False
