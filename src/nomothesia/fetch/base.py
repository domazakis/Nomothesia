"""Πελάτης HTTP με προσωρινή αποθήκευση, επαναλήψεις και ευγενικό ρυθμό.

Κατεβάζουμε από δημόσιους κρατικούς εξυπηρετητές. Δύο κανόνες διέπουν τον
σχεδιασμό:

* **Μη ζητάς ό,τι έχεις ήδη.** Κρατάμε ETag και Last-Modified και στέλνουμε
  conditional GET. Ένα ΦΕΚ του 1983 δεν πρόκειται να αλλάξει· δεν υπάρχει λόγος
  να το ξανακατεβάζουμε κάθε εβδομάδα.
* **Μη χτυπάς γρήγορα.** Παύση ανάμεσα στα αιτήματα, ώστε ο εβδομαδιαίος
  έλεγχος να μη μοιάζει με επίθεση.
"""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from nomothesia.fetch.alysida import (
    SfalmaAlysidas,
    context_me_endiamesa,
    einai_sfalma_alysidas,
    endiamesa_pistopoiitika,
)
from nomothesia.registry import repo_riza

logger = logging.getLogger(__name__)

# Οι κεφαλίδες HTTP είναι ASCII — δεν μπαίνουν ελληνικά εδώ.
USER_AGENT = (
    "Nomothesia/0.1 (public road-traffic legislation collector; "
    "+https://github.com/domazakis/Nomothesia)"
)

PAUSI_METAXY_AITIMATON = 2.0
MEGISTES_PROSPATHEIES = 4
XRONOS_ANAMONIS = 60.0


class SfalmaLipsis(RuntimeError):
    """Η λήψη απέτυχε οριστικά."""


def _minima_apokleismou(url: str, aitia: object) -> str:
    """Εξηγεί τι σημαίνει άρνηση του proxy, αντί για ένα σκέτο σφάλμα δικτύου.

    Είναι η πιο πιθανή αποτυχία όταν το εργαλείο τρέχει μέσα σε cloud συνεδρία
    με περιορισμένη πολιτική εξερχόμενης κίνησης.
    """
    from urllib.parse import urlparse

    domain = urlparse(url).netloc or url
    return (
        f"το δίκτυο απέρριψε τη σύνδεση προς {domain} ({aitia}). "
        f"Αν τρέχεις σε cloud συνεδρία, το domain δεν επιτρέπεται από την "
        f"πολιτική δικτύου του environment. Δες το docs/ENIMEROSI.md για το "
        f"πώς προστίθεται, ή τρέξε την εντολή τοπικά."
    )


@dataclass
class ApotelesmaLipsis:
    perieksomeno: bytes
    url: str
    apo_cache: bool
    typos_perieksomenou: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.perieksomeno).hexdigest()

    @property
    def einai_pdf(self) -> bool:
        return self.perieksomeno[:5] == b"%PDF-"


class Lipsi:
    """Κατεβάζει URL και κρατά αντίγραφο στον φάκελο `.cache/`.

    Ο φάκελος `.cache/` είναι στο .gitignore: είναι αναπαράξιμος και δεν έχει
    θέση στο ιστορικό του repository.
    """

    def __init__(
        self,
        *,
        fakelos_cache: Path | None = None,
        pausi: float = PAUSI_METAXY_AITIMATON,
        timeout: float = 120.0,
    ) -> None:
        self.fakelos_cache = fakelos_cache or (repo_riza() / ".cache")
        self.fakelos_cache.mkdir(parents=True, exist_ok=True)
        self.pausi = pausi
        self.timeout = timeout
        self._teleftaio_aitima = 0.0
        self._epipleon_pem = ""
        self._dokimasmenoi_hosts: set[str] = set()
        self._client = self._neos_client()

    def _neos_client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
            follow_redirects=True,
            verify=context_me_endiamesa(self._epipleon_pem),
        )

    def __enter__(self) -> Lipsi:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ── εσωτερικά ────────────────────────────────────────────────────────
    def _kleidi(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]

    def _diadromi_dedomenon(self, url: str) -> Path:
        return self.fakelos_cache / f"{self._kleidi(url)}.bin"

    def _diadromi_meta(self, url: str) -> Path:
        return self.fakelos_cache / f"{self._kleidi(url)}.json"

    def _symplirose_alysida(self, url: str, exc: Exception) -> bool:
        """Δοκιμάζει να καλύψει ελλιπή αλυσίδα πιστοποιητικών του διακομιστή.

        Επιστρέφει `True` όταν κάτι όντως προστέθηκε, δηλαδή όταν αξίζει άμεση
        επανάληψη. Μία προσπάθεια ανά host: αν δεν έλυσε το πρόβλημα την πρώτη
        φορά, δεν θα το λύσει ούτε την τέταρτη.
        """
        if not einai_sfalma_alysidas(exc):
            return False

        # Ο host που έσπασε δεν είναι κατ' ανάγκη αυτός που ζητήσαμε: το
        # www.et.gr ανακατευθύνει, και η ελλιπής αλυσίδα εμφανίζεται στον
        # επόμενο σταθμό. Το αίτημα της εξαίρεσης ξέρει πού πράγματι πήγαμε.
        aitima = getattr(exc, "request", None)
        diefthynsi = aitima.url if aitima is not None else httpx.URL(url)
        host = diefthynsi.host
        if not host or host in self._dokimasmenoi_hosts:
            return False
        self._dokimasmenoi_hosts.add(host)

        try:
            pem = endiamesa_pistopoiitika(host, port=diefthynsi.port or 443)
        except (SfalmaAlysidas, OSError, ssl.SSLError) as sfalma:
            logger.warning("δεν συμπληρώθηκε η αλυσίδα του %s: %s", host, sfalma)
            return False
        if not pem:
            return False

        logger.info("συμπληρώθηκε η αλυσίδα πιστοποιητικών του %s", host)
        self._epipleon_pem += pem
        self._client.close()
        self._client = self._neos_client()
        return True

    def _aitima(self, url: str, kefalides: dict[str, str]) -> httpx.Response:
        """Το αίτημα, με μία ευκαιρία συμπλήρωσης αλυσίδας ανά host.

        Ο βρόχος τερματίζει από μόνος του: κάθε host δοκιμάζεται μία φορά, οπότε
        μια ανακατεύθυνση με δύο σπασμένες αλυσίδες διορθώνεται σε δύο γύρους
        και η τρίτη αποτυχία βγαίνει προς τα έξω.
        """
        while True:
            try:
                return self._client.get(url, headers=kefalides)
            except httpx.ConnectError as exc:
                if not self._symplirose_alysida(url, exc):
                    raise

    def _perimene(self) -> None:
        perasan = time.monotonic() - self._teleftaio_aitima
        if perasan < self.pausi:
            time.sleep(self.pausi - perasan)
        self._teleftaio_aitima = time.monotonic()

    # ── δημόσιο API ──────────────────────────────────────────────────────
    def _apo_disko(self, url: str) -> ApotelesmaLipsis:
        """Διαβάζει πηγή που βρίσκεται μέσα στο repository (`file:…`)."""
        diadromi = repo_riza() / url.removeprefix("file:").lstrip("/")
        if not diadromi.is_file():
            raise SfalmaLipsis(f"το αρχείο {diadromi} δεν υπάρχει")
        perieksomeno = diadromi.read_bytes()
        typos = "application/pdf" if diadromi.suffix == ".pdf" else "text/html"
        return ApotelesmaLipsis(
            perieksomeno=perieksomeno,
            url=url,
            apo_cache=True,
            typos_perieksomenou=typos,
        )

    def kateveste(self, url: str, *, agnoise_cache: bool = False) -> ApotelesmaLipsis:
        if url.startswith("file:"):
            return self._apo_disko(url)

        diadromi_dedomenon = self._diadromi_dedomenon(url)
        diadromi_meta = self._diadromi_meta(url)

        meta: dict[str, str] = {}
        if diadromi_meta.exists() and not agnoise_cache:
            meta = json.loads(diadromi_meta.read_text(encoding="utf-8"))

        kefalides: dict[str, str] = {}
        if diadromi_dedomenon.exists() and not agnoise_cache:
            if etag := meta.get("etag"):
                kefalides["If-None-Match"] = etag
            if last_modified := meta.get("last_modified"):
                kefalides["If-Modified-Since"] = last_modified

        teleftaio_sfalma: Exception | None = None
        for prospatheia in range(MEGISTES_PROSPATHEIES):
            try:
                self._perimene()
                apantisi = self._aitima(url, kefalides)
            except httpx.ProxyError as exc:
                # Άρνηση πολιτικής δικτύου. Η επανάληψη δεν πρόκειται να
                # βοηθήσει — σταματάμε αμέσως με εξήγηση.
                raise SfalmaLipsis(_minima_apokleismou(url, exc)) from exc
            except httpx.HTTPError as exc:
                teleftaio_sfalma = exc
                time.sleep(2**prospatheia)
                continue

            if apantisi.status_code == 304 and diadromi_dedomenon.exists():
                return ApotelesmaLipsis(
                    perieksomeno=diadromi_dedomenon.read_bytes(),
                    url=url,
                    apo_cache=True,
                    typos_perieksomenou=meta.get("content_type", ""),
                )

            if apantisi.status_code == 429 or apantisi.status_code >= 500:
                teleftaio_sfalma = SfalmaLipsis(
                    f"HTTP {apantisi.status_code} από {url}"
                )
                time.sleep(min(2**prospatheia * 5, XRONOS_ANAMONIS))
                continue

            if apantisi.status_code == 403:
                raise SfalmaLipsis(
                    f"HTTP 403 για {url}. Αν τρέχεις σε cloud συνεδρία, το domain "
                    f"πιθανότατα δεν επιτρέπεται από την πολιτική δικτύου του "
                    f"environment — δες το docs/ENIMEROSI.md."
                )

            # Κάθε σφάλμα γίνεται SfalmaLipsis, που ο αγωγός ξέρει να πιάσει.
            # Το `raise_for_status()` του httpx πετούσε δική του εξαίρεση, η
            # οποία δραπέτευε από τον αγωγό: ένα 404 σε μία πηγή ακύρωνε
            # ολόκληρη την εκτέλεση και τα υπόλοιπα δεκαεννιά νομοθετήματα.
            if apantisi.status_code >= 400:
                raise SfalmaLipsis(f"HTTP {apantisi.status_code} για {url}")

            diadromi_dedomenon.write_bytes(apantisi.content)
            diadromi_meta.write_text(
                json.dumps(
                    {
                        "url": url,
                        "etag": apantisi.headers.get("ETag", ""),
                        "last_modified": apantisi.headers.get("Last-Modified", ""),
                        "content_type": apantisi.headers.get("Content-Type", ""),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return ApotelesmaLipsis(
                perieksomeno=apantisi.content,
                url=url,
                apo_cache=False,
                typos_perieksomenou=apantisi.headers.get("Content-Type", ""),
            )

        # Η αιτία μπαίνει στο μήνυμα, όχι μόνο στο `raise ... from`: η εντολή
        # τρέχει και μέσα σε GitHub Action, όπου το μόνο που μένει είναι το log.
        # Χωρίς αυτήν, ένα timeout και ένα σπασμένο URL μοιάζουν ίδια.
        aitia = (
            f"{type(teleftaio_sfalma).__name__}: {teleftaio_sfalma}"
            if teleftaio_sfalma
            else "άγνωστη αιτία"
        )
        raise SfalmaLipsis(
            f"απέτυχε η λήψη του {url} μετά από {MEGISTES_PROSPATHEIES} "
            f"προσπάθειες ({aitia})"
        ) from teleftaio_sfalma
