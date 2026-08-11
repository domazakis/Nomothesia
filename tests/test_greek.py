"""Έλεγχοι κανονικοποίησης ελληνικού κειμένου από ΦΕΚ."""

from nomothesia.normalize.greek import (
    afairese_thoryvo_selidas,
    diorthose_omografous,
    enose_syllavismo,
    kanonikopoiise,
    kleidi_anazitisis,
)


def test_delta_tou_mathimatikou_symvolou_ginetai_ellinko_delta():
    # Τα ΦΕΚ κωδικοποιούν συχνά το Δ ως U+2206 INCREMENT.
    assert "∆" not in kanonikopoiise("ΕΦΗΜΕΡΙ∆Α")
    assert kanonikopoiise("∆ΙΑΤΑΞΕΙΣ") == "ΔΙΑΤΑΞΕΙΣ"


def test_syllavismos_enonetai():
    assert enose_syllavismo("κυκλοφο-\nρίας") == "κυκλοφορίας"


def test_omografoi_diorthonontai_mesa_se_ellinikes_lexeis():
    # «TΗΣ» με λατινικό T -> ελληνικό Τ
    assert diorthose_omografous("TΗΣ") == "ΤΗΣ"


def test_gnisia_latinika_den_alloionontai():
    # Κρίσιμο: το STOP και το ADR είναι πραγματικά λατινικά και πρέπει να μείνουν.
    keimeno = "πινακίδα STOP και συμφωνία ADR"
    assert "STOP" in diorthose_omografous(keimeno)
    assert "ADR" in diorthose_omografous(keimeno)


def test_thoryvos_selidas_afaireitai():
    keimeno = "ΕΦΗΜΕΡΙΔΑ ΤΗΣ ΚΥΒΕΡΝΗΣΕΩΣ\nΆρθρο 1\n4721\nΚείμενο."
    apotelesma = afairese_thoryvo_selidas(keimeno)
    assert "ΕΦΗΜΕΡΙΔΑ" not in apotelesma
    assert "4721" not in apotelesma
    assert "Άρθρο 1" in apotelesma
    assert "Κείμενο." in apotelesma


def test_arithmos_paragrafou_den_theoreitai_arithmos_selidas():
    # Το «1.» είναι αρχή παραγράφου, όχι αριθμός σελίδας — δεν πρέπει να φύγει.
    assert "1." in afairese_thoryvo_selidas("1. Ο παρών Κώδικας ρυθμίζει.")


def test_kleidi_anazitisis_agnoei_tonous_kai_peza():
    assert kleidi_anazitisis("ΚΥΚΛΟΦΟΡΊΑΣ") == kleidi_anazitisis("κυκλοφορίας")


def test_kleidi_anazitisis_enopoiei_teliko_sigma():
    assert kleidi_anazitisis("οδός") == kleidi_anazitisis("οδοσ")
