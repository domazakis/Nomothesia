"""Ανάγνωση παλαιών δυαδικών `.doc`.

Τα δείγματα φτιάχνονται εδώ byte προς byte αντί να φυλάσσονται ως αρχεία: έτσι
φαίνεται τι ακριβώς λέει η προδιαγραφή για κάθε πεδίο, και ένα αποτυχημένο test
δείχνει ποιο πεδίο παρανοήθηκε αντί για «το δείγμα δεν διαβάζεται».
"""

from __future__ import annotations

import struct

import pytest

from nomothesia.extract.doc import (
    SfalmaDoc,
    einai_doc,
    keimeno_apo_streams,
)

# Το FIB μέχρι και το ζεύγος fcClx/lcbClx. Οι θέσεις προκύπτουν από τα δηλωμένα
# μεγέθη csw/cslw, όπως ακριβώς τις υπολογίζει ο κώδικας.
CSW = 14
CSLW = 22
THESI_CSLW = 0x22 + CSW * 2
THESI_FIB_RG_LW = THESI_CSLW + 2
THESI_BLOB = THESI_FIB_RG_LW + CSLW * 4 + 2
THESI_FC_CLX = THESI_BLOB + 33 * 8
MEGETHOS_FIB = THESI_FC_CLX + 8


def _fib(
    *, keimeno: bytes, plithos_cp: int, fc_clx: int, ellinika: bool = True
) -> bytes:
    """Ένα stream «WordDocument»: FIB και μετά το κείμενο."""
    fib = bytearray(MEGETHOS_FIB)
    struct.pack_into("<H", fib, 0, 0xA5EC)  # wIdent
    struct.pack_into("<H", fib, 6, 0x0408 if ellinika else 0x0409)  # lid
    struct.pack_into("<H", fib, 0x0A, 0x0200)  # ενεργό stream: 1Table
    struct.pack_into("<H", fib, 0x20, CSW)
    struct.pack_into("<H", fib, THESI_CSLW, CSLW)
    struct.pack_into("<I", fib, THESI_FIB_RG_LW + 12, plithos_cp)  # ccpText
    struct.pack_into("<I", fib, THESI_FC_CLX, fc_clx)
    struct.pack_into("<I", fib, THESI_FC_CLX + 4, 0)  # lcbClx: συμπληρώνεται μετά
    return bytes(fib) + keimeno


def _clx(kommatia: list[tuple[int, int, bool]], teliko_cp: int) -> bytes:
    """Ένα Clx με μόνο τον piece table.

    Κάθε κομμάτι δίνεται ως (πρώτος χαρακτήρας, θέση στο stream, συμπιεσμένο).
    """
    cps = [arxi for arxi, _, _ in kommatia] + [teliko_cp]
    plc = b"".join(struct.pack("<I", cp) for cp in cps)
    for _, fc, sympiesmeno in kommatia:
        akatergasto = (fc * 2) | 0x40000000 if sympiesmeno else fc
        plc += struct.pack("<HIH", 0, akatergasto, 0)
    return bytes([0x02]) + struct.pack("<I", len(plc)) + plc


def _egrafo(
    keimeno: bytes,
    kommatia: list[tuple[int, int, bool]],
    plithos_cp: int,
    *,
    ellinika: bool = True,
    prin_apo_ton_pinaka: bytes = b"",
) -> tuple[bytes, bytes]:
    """Το ζεύγος streams που περιμένει ο αναγνώστης."""
    clx = prin_apo_ton_pinaka + _clx(kommatia, plithos_cp)
    egrafo = bytearray(
        _fib(keimeno=keimeno, plithos_cp=plithos_cp, fc_clx=0, ellinika=ellinika)
    )
    struct.pack_into("<I", egrafo, THESI_FC_CLX + 4, len(clx))
    return bytes(egrafo), clx


def test_diavazei_ellinika_se_utf16():
    """Η συνήθης περίπτωση: ελληνικό κείμενο σε δύο bytes ανά χαρακτήρα."""
    soma = "Άρθρο 1\rΤο όχημα ασφαλίζεται.\r"
    egrafo, pinakas = _egrafo(
        soma.encode("utf-16-le"), [(0, MEGETHOS_FIB, False)], len(soma)
    )

    assert keimeno_apo_streams(egrafo, pinakas) == "Άρθρο 1\nΤο όχημα ασφαλίζεται.\n"


def test_diavazei_ellinika_se_sympiesmeni_morfi():
    """Το συμπιεσμένο κείμενο ελληνικού εγγράφου διαβάζεται ως cp1253.

    Ο ίδιος byte που σε cp1252 δίνει «Ã» εδώ πρέπει να δώσει «Γ». Αν η επιλογή
    σελίδας κώδικα σπάσει, αυτό το test το δείχνει αμέσως.
    """
    soma = "Άρθρο 2\rΓενικά.\r"
    egrafo, pinakas = _egrafo(
        soma.encode("cp1253"), [(0, MEGETHOS_FIB, True)], len(soma)
    )

    assert keimeno_apo_streams(egrafo, pinakas) == "Άρθρο 2\nΓενικά.\n"


def test_se_mi_elliniko_egrafo_i_kodikoselida_einai_i_dytiki():
    """Η γλώσσα του εγγράφου, όχι η καταγωγή του έργου, ορίζει τη σελίδα κώδικα."""
    soma = "Résumé"
    egrafo, pinakas = _egrafo(
        soma.encode("cp1252"),
        [(0, MEGETHOS_FIB, True)],
        len(soma),
        ellinika=False,
    )

    assert keimeno_apo_streams(egrafo, pinakas) == soma


def test_ta_kommatia_enonontai_me_ti_seira_tou_pinaka():
    """Η σειρά του κειμένου είναι αυτή του piece table, όχι του stream.

    Εδώ το δεύτερο κομμάτι είναι αποθηκευμένο **πριν** από το πρώτο. Ένας
    αναγνώστης που απλώς διαβάζει το stream από την αρχή θα τα έδινε ανάποδα.
    """
    deftero = "δεύτερο.".encode("utf-16-le")
    proto = "Πρώτο ".encode("utf-16-le")
    egrafo, pinakas = _egrafo(
        deftero + proto,
        [
            (0, MEGETHOS_FIB + len(deftero), False),
            (6, MEGETHOS_FIB, False),
        ],
        14,
    )

    assert keimeno_apo_streams(egrafo, pinakas) == "Πρώτο δεύτερο."


def test_stamata_sto_kyrios_soma():
    """Υποσημειώσεις και κεφαλίδες ακολουθούν το σώμα και δεν μας αφορούν."""
    egrafo, pinakas = _egrafo(
        "Άρθρο 1.\rσελίδα 3".encode("utf-16-le"),
        [(0, MEGETHOS_FIB, False)],
        len("Άρθρο 1.\r"),
    )

    assert keimeno_apo_streams(egrafo, pinakas) == "Άρθρο 1.\n"


def test_agnoei_tin_odigia_pediou():
    """Η οδηγία ενός πεδίου είναι κώδικας του Word, όχι κείμενο του νόμου."""
    soma = "Άρθρο \x13PAGE\x141\x15 του π.δ."
    egrafo, pinakas = _egrafo(
        soma.encode("utf-16-le"), [(0, MEGETHOS_FIB, False)], len(soma)
    )

    assert keimeno_apo_streams(egrafo, pinakas) == "Άρθρο 1 του π.δ."


def test_prosperna_tis_omades_idiotiton():
    """Πριν από τον piece table μπορεί να υπάρχουν ομάδες ιδιοτήτων.

    Έχουν μεταβλητό μήκος· αν δεν προσπεραστούν σωστά, ο πίνακας διαβάζεται
    από λάθος θέση και το έγγραφο μοιάζει κατεστραμμένο.
    """
    soma = "Άρθρο 3\r"
    idiotites = bytes([0x01]) + struct.pack("<h", 6) + b"\x00" * 6
    egrafo, pinakas = _egrafo(
        soma.encode("utf-16-le"),
        [(0, MEGETHOS_FIB, False)],
        len(soma),
        prin_apo_ton_pinaka=idiotites,
    )

    assert keimeno_apo_streams(egrafo, pinakas) == "Άρθρο 3\n"


def test_arnitai_arxeio_pou_den_einai_word():
    with pytest.raises(SfalmaDoc, match="FIB"):
        keimeno_apo_streams(b"%PDF-1.4 ...", b"")


def test_arnitai_egrafo_choris_piece_table():
    egrafo, _ = _egrafo("κάτι".encode("utf-16-le"), [(0, MEGETHOS_FIB, False)], 4)

    with pytest.raises(SfalmaDoc, match="piece table"):
        keimeno_apo_streams(egrafo, b"")


def test_i_anagnorisi_thelei_stream_word():
    """Τα `.xls` της ίδιας εποχής έχουν την ίδια υπογραφή OLE."""
    assert not einai_doc(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512)
    assert not einai_doc(b"%PDF-1.4")
