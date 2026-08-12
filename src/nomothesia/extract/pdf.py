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
# Ανεκτικότητα σε λέξεις που όντως διασχίζουν το αυλάκι (τίτλοι σε όλο το
# πλάτος, κεφαλίδα σελίδας). Πάνω από αυτό το ποσοστό, η σελίδα είναι μονόστηλη.
ANEKTIKOTITA_DIASCHISIS = 0.02
# Πού αναζητείται το αυλάκι, ως ποσοστό του πλάτους της σελίδας.
ORIA_AVLAKIOU = range(35, 66)
# Οι κεντραρισμένες επικεφαλίδες των ΦΕΚ τυπώνονται πιο πυκνά από το σώμα, και
# με την προεπιλογή του pdfplumber τα κενά τους χάνονται: ο τίτλος «Λογιστικός
# διαχωρισμός» έβγαινε «Λογιστικόςδιαχωρισμός». Το σώμα δεν επηρεάζεται.
ANOCHI_KENOU = 2


def _avlaki(selida) -> float | None:
    """Η θέση του κατακόρυφου αυλακιού ανάμεσα στις στήλες, ή `None`.

    Το αυλάκι **δεν είναι πάντα στο κέντρο**. Στο ΦΕΚ Α΄82/2012 βρίσκεται στο
    53% του πλάτους: εκεί το διασχίζει μία λέξη, ενώ στο κέντρο σαράντα έξι.
    Υποθέτοντας το μέσο, η σελίδα κρινόταν μονόστηλη και οι δύο στήλες
    διαβάζονταν πλεγμένες μεταξύ τους — από τις 740 χιλιάδες χαρακτήρες του
    νόμου εντοπίζονταν δεκαπέντε άρθρα.

    Γι' αυτό το αυλάκι αναζητείται αντί να υποτίθεται: δοκιμάζονται θέσεις
    γύρω από το μέσο και κρατιέται εκείνη που τη διασχίζουν οι λιγότερες
    λέξεις. Όταν καμία θέση δεν είναι αρκετά «καθαρή», η σελίδα είναι
    μονόστηλη.
    """
    lexeis = selida.extract_words() or []
    if len(lexeis) < ELAXISTES_LEXEIS:
        return None

    orizontia = [(float(w["x0"]), float(w["x1"])) for w in lexeis]
    platos = float(selida.width)

    metriseis = []
    for pososto in ORIA_AVLAKIOU:
        thesi = platos * pososto / 100
        metriseis.append((sum(1 for a, b in orizontia if a < thesi < b), thesi))

    ligotera = min(m[0] for m in metriseis)
    if ligotera / len(lexeis) >= ANEKTIKOTITA_DIASCHISIS:
        return None

    # Όταν το αυλάκι είναι φαρδύ, πολλές θέσεις ισοβαθμούν. Κρατάμε τη μεσαία,
    # ώστε η τομή να πέσει στο κέντρο του κενού και όχι στο χείλος του.
    isovathmes = sorted(thesi for plithos, thesi in metriseis if plithos == ligotera)
    return isovathmes[len(isovathmes) // 2]


def _keimeno_stilis(selida, x0: float, x1: float) -> str:
    perioxi = selida.crop((x0, 0, x1, selida.height))
    return perioxi.extract_text(x_tolerance=ANOCHI_KENOU) or ""


def keimeno_apo_pdf(dedomena: bytes) -> str:
    """Επιστρέφει το κείμενο ολόκληρου του PDF, σεβόμενο τις στήλες.

    Δεν κάνει κανονικοποίηση — αυτή είναι δουλειά του `normalize.greek`.
    """
    kommatia: list[str] = []

    with pdfplumber.open(io.BytesIO(dedomena)) as pdf:
        for arithmos, selida in enumerate(pdf.pages, start=1):
            try:
                if (avlaki := _avlaki(selida)) is not None:
                    kommatia.append(_keimeno_stilis(selida, 0, avlaki))
                    kommatia.append(_keimeno_stilis(selida, avlaki, float(selida.width)))
                else:
                    kommatia.append(
                        selida.extract_text(x_tolerance=ANOCHI_KENOU) or ""
                    )
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
