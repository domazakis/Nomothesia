"""Έλεγχος της συμπλήρωσης ελλιπούς αλυσίδας πιστοποιητικών.

Στήνεται τοπικό PKI — ρίζα, ενδιάμεσο, πιστοποιητικό διακομιστή — και τοπικός
διακομιστής TLS που σερβίρει μόνο το τελευταίο, ακριβώς όπως ο διακομιστής που
μας απασχολεί στην πράξη. Κανένα από τα tests δεν αγγίζει δίκτυο πέρα από το
`localhost`.

Το κρίσιμο test είναι το `test_ena_endiameso_den_ginetai_simeio_empistosynis`:
ολόκληρη η ασφάλεια του `fetch/alysida.py` στηρίζεται στο ότι ένα προστεθειμένο
ενδιάμεσο **δεν** αρκεί από μόνο του για να εγκριθεί μια σύνδεση. Αν αυτή η
ιδιότητα αλλάξει ποτέ, η προσθήκη γίνεται επικίνδυνη και πρέπει να το μάθουμε
από εδώ.
"""

from __future__ import annotations

import datetime as dt
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID

from nomothesia.fetch.alysida import (
    _fortose,
    _url_ekdoti,
    context_me_endiamesa,
    einai_sfalma_alysidas,
)

AIA_URL = "http://pistopoiitika.example/endiameso.crt"


def _onoma(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _ftiakse(
    cn: str,
    ekdotis: x509.Name,
    kleidi_ekdoti,
    *,
    ca: bool,
    san: str | None = None,
    aia: str | None = None,
):
    kleidi = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tora = dt.datetime.now(dt.UTC)
    ktistis = (
        x509.CertificateBuilder()
        .subject_name(_onoma(cn))
        .issuer_name(ekdotis)
        .public_key(kleidi.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(tora - dt.timedelta(days=1))
        .not_valid_after(tora + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    if san:
        ktistis = ktistis.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(san)]), critical=False
        )
    if aia:
        ktistis = ktistis.add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.CA_ISSUERS,
                        x509.UniformResourceIdentifier(aia),
                    )
                ]
            ),
            critical=False,
        )
    return ktistis.sign(kleidi_ekdoti or kleidi, hashes.SHA256()), kleidi


@pytest.fixture(scope="module")
def pki():
    """Ρίζα → ενδιάμεσο → πιστοποιητικό διακομιστή."""
    riza, riza_kleidi = _ftiakse("Riza Dokimis", _onoma("Riza Dokimis"), None, ca=True)
    endiameso, endiameso_kleidi = _ftiakse(
        "Endiameso Dokimis", riza.subject, riza_kleidi, ca=True
    )
    diakomistis, diakomisti_kleidi = _ftiakse(
        "localhost", endiameso.subject, endiameso_kleidi, ca=False, san="localhost", aia=AIA_URL
    )
    return {
        "riza": riza,
        "endiameso": endiameso,
        "diakomistis": diakomistis,
        "diakomisti_kleidi": diakomisti_kleidi,
    }


def _pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


@pytest.fixture(scope="module")
def elleipis_diakomistis(pki, tmp_path_factory):
    """Διακομιστής TLS που σερβίρει μόνο το δικό του πιστοποιητικό."""
    fakelos = tmp_path_factory.mktemp("tls")
    diadromi = fakelos / "diakomistis.pem"
    diadromi.write_text(
        _pem(pki["diakomistis"])
        + pki["diakomisti_kleidi"]
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        .decode("ascii")
    )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(diadromi)

    ypodochi = socket.socket()
    ypodochi.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ypodochi.bind(("127.0.0.1", 0))
    ypodochi.listen(8)

    def serve() -> None:
        while True:
            try:
                syndesi, _ = ypodochi.accept()
            except OSError:
                return
            try:
                context.wrap_socket(syndesi, server_side=True).close()
            except OSError:
                syndesi.close()

    threading.Thread(target=serve, daemon=True).start()
    yield ypodochi.getsockname()[1]
    ypodochi.close()


def _syndese(thyra: int, cadata: str | None) -> str | None:
    """Επιστρέφει `None` σε επιτυχία, αλλιώς τον λόγο της αποτυχίας."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # άδειο απόθεμα επίτηδες
    context.verify_mode = ssl.CERT_REQUIRED
    if cadata:
        context.load_verify_locations(cadata=cadata)
    try:
        with socket.create_connection(("127.0.0.1", thyra), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="localhost"):
                return None
    except ssl.SSLError as exc:
        return exc.reason or str(exc)


def test_elleipis_alysida_apotygchanei_choris_to_endiameso(pki, elleipis_diakomistis):
    """Η συνθήκη που μας απασχολεί: η ρίζα είναι έμπιστη, λείπει το ενδιάμεσο."""
    assert _syndese(elleipis_diakomistis, _pem(pki["riza"])) == "CERTIFICATE_VERIFY_FAILED"


def test_ena_endiameso_den_ginetai_simeio_empistosynis(pki, elleipis_diakomistis):
    """Χωρίς έμπιστη ρίζα, το ενδιάμεσο δεν εγκρίνει από μόνο του τη σύνδεση.

    Αν αυτό αλλάξει, ένας κακόβουλος διακομιστής θα μπορούσε να μας υποδείξει
    μέσω AIA δικό του «ενδιάμεσο» και να γίνει έμπιστος. Δες `fetch/alysida.py`.
    """
    assert _syndese(elleipis_diakomistis, _pem(pki["endiameso"])) == "CERTIFICATE_VERIFY_FAILED"


def test_i_symplirosi_tis_alysidas_lynei_ti_syndesi(pki, elleipis_diakomistis):
    cadata = _pem(pki["riza"]) + _pem(pki["endiameso"])
    assert _syndese(elleipis_diakomistis, cadata) is None


def test_vriskei_to_url_tou_ekdoti(pki):
    assert _url_ekdoti(pki["diakomistis"]) == AIA_URL


def test_choris_aia_den_yparchei_url(pki):
    assert _url_ekdoti(pki["riza"]) is None


def test_fortonei_der_kai_pem(pki):
    endiameso = pki["endiameso"]
    der = endiameso.public_bytes(serialization.Encoding.DER)
    assert _fortose(der).subject == endiameso.subject
    assert _fortose(_pem(endiameso).encode()).subject == endiameso.subject


def test_agnosti_morfi_den_skaei():
    assert _fortose(b"kati alo entelos") is None


def test_context_periechei_ta_endiamesa(pki):
    context = context_me_endiamesa(_pem(pki["endiameso"]))
    themata = {
        cert["subject"][-1][0][1] for cert in context.get_ca_certs() if cert.get("subject")
    }
    assert "Endiameso Dokimis" in themata


@pytest.mark.parametrize(
    ("minima", "anamenomeno"),
    [
        ("[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate", True),
        ("[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired", False),
        ("[SSL: CERTIFICATE_VERIFY_FAILED] self signed certificate", False),
        ("Connection refused", False),
    ],
)
def test_xechorizei_poia_sfalmata_afopoun_tin_alysida(minima, anamenomeno):
    """Ληγμένο ή πλαστό πιστοποιητικό δεν διορθώνεται με κατέβασμα ενδιάμεσου."""
    assert einai_sfalma_alysidas(OSError(minima)) is anamenomeno
