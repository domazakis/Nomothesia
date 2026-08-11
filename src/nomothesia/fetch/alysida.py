"""Συμπλήρωση ελλιπούς αλυσίδας πιστοποιητικών.

Ο διακομιστής του `et.gr` στέλνει μόνο το δικό του πιστοποιητικό και παραλείπει
το ενδιάμεσο που το συνδέει με τη ρίζα. Ο browser το καλύπτει σιωπηλά: διαβάζει
το πεδίο *Authority Information Access* και κατεβάζει μόνος του ό,τι λείπει. Η
Python δεν το κάνει, οπότε η σύνδεση πέφτει με `CERTIFICATE_VERIFY_FAILED` και ο
νόμος μοιάζει απρόσιτος ενώ ανοίγει μια χαρά στον browser.

Εδώ κάνουμε ό,τι κάνει ο browser, **χωρίς να χαλαρώσουμε τον έλεγχο**.

Η ανασφάλιστη σύνδεση χρησιμεύει μόνο για να διαβαστεί ποιο πιστοποιητικό
λείπει· δεν κατεβαίνει τίποτα μέσα από αυτήν. Το ενδιάμεσο που βρίσκουμε
προστίθεται στο απόθεμα και η πραγματική λήψη γίνεται με πλήρη επαλήθευση.

Δύο κανόνες κρατούν την προσθήκη ακίνδυνη:

* **Οι αυτο-υπογεγραμμένες ρίζες δεν προστίθενται ποτέ.** Αλλιώς θα αρκούσε ένας
  διακομιστής να μας στείλει τη ρίζα της αρεσκείας του για να τον εμπιστευτούμε.
* **Ένα ενδιάμεσο δεν αρκεί από μόνο του.** Το OpenSSL απαιτεί η αλυσίδα να
  καταλήγει σε αυτο-υπογεγραμμένη ρίζα του αποθέματος· ένα ενδιάμεσο απλώς
  γεφυρώνει ως εκεί. Το `tests/test_alysida.py` το επιβεβαιώνει με τοπικό PKI,
  γιατί πάνω σε αυτή την ιδιότητα στηρίζεται η ασφάλεια ολόκληρου του αρχείου.
"""

from __future__ import annotations

import logging
import socket
import ssl

import certifi
import httpx
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

logger = logging.getLogger(__name__)

# Οι πραγματικές αλυσίδες έχουν ένα ή δύο ενδιάμεσα. Το όριο υπάρχει για να μην
# κυνηγήσουμε επ' άπειρον έναν διακομιστή που δείχνει στον εαυτό του.
MEGISTO_VATHOS = 4


class SfalmaAlysidas(RuntimeError):
    """Δεν κατέστη δυνατό να συμπληρωθεί η αλυσίδα."""


def einai_sfalma_alysidas(exc: BaseException) -> bool:
    """Ξεχωρίζει το «λείπει ενδιάμεσο» από τα υπόλοιπα σφάλματα TLS.

    Ένα ληγμένο ή πλαστό πιστοποιητικό δεν διορθώνεται με κατέβασμα ενδιάμεσου —
    και δεν πρέπει να το προσπαθήσουμε καν.
    """
    minima = str(exc)
    return (
        "unable to get local issuer certificate" in minima
        or "unable to get issuer certificate" in minima
    )


def _pistopoiitiko_diakomisti(host: str, port: int, timeout: float) -> x509.Certificate:
    """Διαβάζει το πιστοποιητικό που παρουσιάζει ο διακομιστής, χωρίς επαλήθευση.

    Δεν το εμπιστευόμαστε: το χρησιμοποιούμε αποκλειστικά για να μάθουμε ποιος
    το εξέδωσε. Οτιδήποτε κατεβεί ύστερα ελέγχεται κανονικά.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise SfalmaAlysidas(f"ο {host} δεν παρουσίασε πιστοποιητικό")
    return x509.load_der_x509_certificate(der)


def _url_ekdoti(cert: x509.Certificate) -> str | None:
    """Το `caIssuers` URL του πιστοποιητικού, αν το δηλώνει."""
    try:
        epektasi = cert.extensions.get_extension_for_oid(
            ExtensionOID.AUTHORITY_INFORMATION_ACCESS
        )
    except x509.ExtensionNotFound:
        return None
    for perigrafi in epektasi.value:
        if perigrafi.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
            return str(perigrafi.access_location.value)
    return None


def _fortose(perieksomeno: bytes) -> x509.Certificate | None:
    """Δέχεται τις τρεις μορφές που σερβίρουν στην πράξη οι αρχές: DER, PEM, PKCS#7."""
    for fortotis in (x509.load_der_x509_certificate, x509.load_pem_x509_certificate):
        try:
            return fortotis(perieksomeno)
        except ValueError:
            continue
    try:
        pistopoiitika = pkcs7.load_der_pkcs7_certificates(perieksomeno)
    except ValueError:
        return None
    return pistopoiitika[0] if pistopoiitika else None


def _einai_riza(cert: x509.Certificate) -> bool:
    return cert.issuer == cert.subject


def endiamesa_pistopoiitika(host: str, *, port: int = 443, timeout: float = 30.0) -> str:
    """Κατεβάζει τα ενδιάμεσα που λείπουν και τα επιστρέφει ως PEM.

    Αν δεν βρεθεί τίποτα προσθετέο, σηκώνει `SfalmaAlysidas` με τον λόγο: ο
    διακομιστής δεν δηλώνει εκδότη, ή το μόνο που λείπει είναι ρίζα — που δεν
    την προσθέτουμε ποτέ, οπότε το πρόβλημα βρίσκεται στο απόθεμα του
    συστήματος και όχι εδώ.
    """
    cert = _pistopoiitiko_diakomisti(host, port, timeout)
    kommatia: list[str] = []
    aitia = ""

    for _ in range(MEGISTO_VATHOS):
        url = _url_ekdoti(cert)
        if not url:
            aitia = (
                f"το πιστοποιητικό δεν δηλώνει από πού κατεβαίνει ο εκδότης του "
                f"({cert.issuer.rfc4514_string()})"
            )
            break
        try:
            apantisi = httpx.get(url, timeout=timeout, follow_redirects=True)
            apantisi.raise_for_status()
        except httpx.HTTPError as exc:
            raise SfalmaAlysidas(f"δεν κατέβηκε το πιστοποιητικό από {url}: {exc}") from exc

        ekdotis = _fortose(apantisi.content)
        if ekdotis is None:
            raise SfalmaAlysidas(f"το {url} δεν περιέχει αναγνωρίσιμο πιστοποιητικό")
        if _einai_riza(ekdotis):
            # Ρίζα: σταματάμε χωρίς να την προσθέσουμε. Εμπιστευόμαστε μόνο το
            # απόθεμα του συστήματος.
            aitia = (
                f"ο εκδότης είναι αυτο-υπογεγραμμένη ρίζα "
                f"({ekdotis.subject.rfc4514_string()}) και δεν την προσθέτουμε — "
                f"αν η σύνδεση εξακολουθεί να πέφτει, η ρίζα λείπει από το "
                f"απόθεμα του συστήματος"
            )
            break

        kommatia.append(ekdotis.public_bytes(Encoding.PEM).decode("ascii"))
        cert = ekdotis

    if not kommatia:
        # Σιωπηλή αποτυχία εδώ σημαίνει ότι το επόμενο άτομο ξαναρχίζει την
        # έρευνα από το μηδέν. Ο λόγος λέγεται.
        raise SfalmaAlysidas(aitia or "δεν βρέθηκε ενδιάμεσο προς προσθήκη")
    return "".join(kommatia)


def context_me_endiamesa(pem: str) -> ssl.SSLContext:
    """Κανονικό context επαλήθευσης, με τα ενδιάμεσα προστεθειμένα."""
    context = ssl.create_default_context(cafile=certifi.where())
    if pem:
        context.load_verify_locations(cadata=pem)
    return context
