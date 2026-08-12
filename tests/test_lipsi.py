"""Έλεγχοι του πελάτη λήψης, με προσομοιωμένες απαντήσεις HTTP.

Καμία δοκιμή δεν αγγίζει δίκτυο: το `httpx.MockTransport` απαντά τοπικά.
"""

from __future__ import annotations

import httpx
import pytest

from nomothesia.fetch.base import Lipsi, SfalmaLipsis


def _lipsi(handler, tmp_path) -> Lipsi:
    lipsi = Lipsi(fakelos_cache=tmp_path / "cache", pausi=0.0)
    lipsi._client.close()
    lipsi._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lipsi


def test_katevazei_kai_apothikevei(tmp_path):
    with _lipsi(lambda _: httpx.Response(200, content=b"NOMOS"), tmp_path) as lipsi:
        apotelesma = lipsi.kateveste("https://paradeigma.gr/nomos")
    assert apotelesma.perieksomeno == b"NOMOS"
    assert apotelesma.apo_cache is False


# ── Σφάλματα HTTP ────────────────────────────────────────────────────────
#
# Μια σελίδα που έφυγε δεν πρέπει να ρίχνει την εκτέλεση. Το `raise_for_status()`
# πετούσε εξαίρεση του httpx, την οποία ο αγωγός δεν έπιανε: ένα 404 σε μία πηγή
# ακύρωνε και τα υπόλοιπα δεκαεννιά νομοθετήματα.


@pytest.mark.parametrize("kodikas", [404, 400, 410])
def test_sfalma_pelati_ginetai_sfalma_lipsis(kodikas, tmp_path):
    with _lipsi(lambda _: httpx.Response(kodikas), tmp_path) as lipsi:
        with pytest.raises(SfalmaLipsis, match=str(kodikas)):
            lipsi.kateveste("https://paradeigma.gr/pou-efyge")


def test_to_403_exigei_tin_politiki_diktyou(tmp_path):
    with _lipsi(lambda _: httpx.Response(403), tmp_path) as lipsi:
        with pytest.raises(SfalmaLipsis, match="ENIMEROSI"):
            lipsi.kateveste("https://paradeigma.gr/apagorevmeno")


def test_to_500_epanalamvanetai_kai_meta_apotygchanei(tmp_path, monkeypatch):
    # Χωρίς αυτό, η δοκιμή περιμένει πραγματικά τα 35 δευτερόλεπτα της υποχώρησης.
    monkeypatch.setattr("nomothesia.fetch.base.time.sleep", lambda _: None)
    prospatheies = []

    def handler(aitima: httpx.Request) -> httpx.Response:
        prospatheies.append(aitima.url)
        return httpx.Response(503)

    lipsi = _lipsi(handler, tmp_path)
    lipsi.__exit__ = lambda *_: None
    with pytest.raises(SfalmaLipsis, match="προσπάθειες"):
        lipsi.kateveste("https://paradeigma.gr/pesmeno")
    assert len(prospatheies) > 1, "τα 5xx είναι προσωρινά και αξίζουν επανάληψη"


def test_to_304_epistrefei_to_apothikevmeno(tmp_path):
    apantiseis = [
        httpx.Response(200, content=b"PALIO", headers={"ETag": "abc"}),
        httpx.Response(304),
    ]
    with _lipsi(lambda _: apantiseis.pop(0), tmp_path) as lipsi:
        lipsi.kateveste("https://paradeigma.gr/statheros")
        deftero = lipsi.kateveste("https://paradeigma.gr/statheros")
    assert deftero.perieksomeno == b"PALIO"
    assert deftero.apo_cache is True


# ── Τοπικές πηγές ────────────────────────────────────────────────────────


def test_diavazei_topiko_arxeio(tmp_path, monkeypatch):
    # Το base.py εισάγει τη συνάρτηση απευθείας, οπότε εκεί μπαίνει το υποκατάστατο.
    monkeypatch.setattr("nomothesia.fetch.base.repo_riza", lambda: tmp_path)
    (tmp_path / "sources" / "fek").mkdir(parents=True)
    (tmp_path / "sources" / "fek" / "deigma.pdf").write_bytes(b"%PDF-1.4 psefto")

    with _lipsi(lambda _: httpx.Response(500), tmp_path) as lipsi:
        apotelesma = lipsi.kateveste("file:sources/fek/deigma.pdf")

    assert apotelesma.einai_pdf
    assert apotelesma.typos_perieksomenou == "application/pdf"


def test_topiko_arxeio_pou_leipei_to_leei_katharu(tmp_path, monkeypatch):
    monkeypatch.setattr("nomothesia.fetch.base.repo_riza", lambda: tmp_path)
    with _lipsi(lambda _: httpx.Response(200), tmp_path) as lipsi:
        with pytest.raises(SfalmaLipsis, match="δεν υπάρχει"):
            lipsi.kateveste("file:sources/fek/anyparkto.pdf")
