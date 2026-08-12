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


def test_o_deiktis_tis_vasis_ginetai_epikefalida():
    """Στις εξαγωγές της βάσης ΝΟΜΟΣ η επικεφαλίδα κρύβεται μέσα στη γραμμή.

    Το «Αρθρο :8» κολλάει στο σχόλιο του προηγούμενου άρθρου, οπότε η κανονική
    επικεφαλίδα που ακολουθεί δεν βρίσκεται ποτέ στην αρχή γραμμής και το
    άρθρο χάνεται ολόκληρο.
    """
    akatergasto = (
        '*** Το άρθρο 7 αντικαταστάθηκε με το ΠΔ 264/1991. Αρθρο :8 '
        'Πληροφορίες Νομολογίας & Αρθρογραφίας :1 Προισχύσασες μορφές '
        'άρθρου :2 "Άρθρο 8\n1. Αν μεταβιβαστεί η κυριότητα του οχήματος.'
    )

    kanoniko = kanonikopoiise(akatergasto)

    assert "Άρθρο 8" in kanoniko.split("\n")
    assert "Πληροφορίες" not in kanoniko
    assert "Προισχύσασες" not in kanoniko


def test_to_proimio_tis_vasis_den_ginetai_arthro_miden():
    """Το «Αρθρο :0» της βάσης στεγάζει το προοίμιο, όχι άρθρο."""
    kanoniko = kanonikopoiise("Τίτλος νομοθετήματος Αρθρο :0 Έχοντας υπόψη:")

    assert "Άρθρο 0" not in kanoniko
    assert "Έχοντας υπόψη" in kanoniko


def test_i_epanalipsi_tis_epikefalidas_den_ginetai_titlos():
    """Μετά τον δείκτη, το έγγραφο ξαναγράφει μόνο του την επικεφαλίδα."""
    kanoniko = kanonikopoiise('Αρθρο :34 "Αρθρο 34 Με απόφαση του Υπουργού.')

    assert kanoniko.startswith("Άρθρο 34\n")
    assert "Με απόφαση του Υπουργού." in kanoniko
    assert kanoniko.count("34") == 1
