"""Φόρτωση και έλεγχος εγκυρότητας του μητρώου πηγών (`sources/registry.yaml`).

Το μητρώο είναι η μοναδική πηγή αλήθειας: ποια νομοθετήματα μας αφορούν, πού
βρίσκονται, πότε ισχύουν και πώς σχετίζονται μεταξύ τους. Ο υπόλοιπος κώδικας
δεν έχει hardcoded URLs.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

# Κωδικοί τευχών όπως τους περιμένει το DownloadFeksApi του Εθνικού Τυπογραφείου.
# Τα κλειδιά γράφονται με λατινικούς χαρακτήρες για να πληκτρολογούνται εύκολα
# στο YAML· η εμφάνιση προς τον χρήστη γίνεται πάντα με ελληνικά (TEUXOS_ELLINIKA).
TEUXOS_KODIKOI: dict[str, str] = {
    "A": "01",  # Πρώτο — νόμοι, προεδρικά διατάγματα
    "B": "02",  # Δεύτερο — υπουργικές αποφάσεις
    "C": "03",
    "D": "04",
}

TEUXOS_ELLINIKA: dict[str, str] = {"A": "Α", "B": "Β", "C": "Γ", "D": "Δ"}


def repo_riza() -> Path:
    """Η ρίζα του repository, ανεξάρτητα από το πού τρέχει η εντολή."""
    return Path(__file__).resolve().parents[2]


class Typos(StrEnum):
    NOMOS = "nomos"
    PD = "pd"
    YA = "ya"
    KYA = "kya"
    KANONISMOS_EE = "kanonismos_ee"
    ODIGIA_EE = "odigia_ee"


class Katastasi(StrEnum):
    ISXYON = "isxyon"          # ισχύει σήμερα
    KATARGIMENO = "katargimeno"  # καταργήθηκε ρητά
    ISTORIKO = "istoriko"       # διατηρείται για μεταβατικούς/ιστορικούς λόγους


class TyposPigis(StrEnum):
    FEK_PDF = "fek_pdf"
    KODIKOPOIIMENO_HTML = "kodikopoiimeno_html"
    EURLEX_HTML = "eurlex_html"
    PDF_ALLI_PIGI = "pdf_alli_pigi"


class Fek(BaseModel):
    """Παραπομπή σε Φύλλο Εφημερίδας της Κυβερνήσεως."""

    teuxos: str
    arithmos: int
    imerominia: dt.date

    @field_validator("teuxos")
    @classmethod
    def _elegxos_teuxous(cls, v: str) -> str:
        if v not in TEUXOS_KODIKOI:
            epitrepta = ", ".join(TEUXOS_KODIKOI)
            raise ValueError(f"άγνωστο τεύχος ΦΕΚ {v!r}· επιτρεπτά: {epitrepta}")
        return v

    @property
    def pdf_id(self) -> str:
        """Το αναγνωριστικό που δέχεται το `DownloadFeksApi` του et.gr.

        Μορφή: ΕΤΟΣ(4) + ΤΕΥΧΟΣ(2) + ΑΡΙΘΜΟΣ(5, με μηδενικά μπροστά).
        Π.χ. ΦΕΚ Α΄100/2025 -> 20250100100
        """
        return f"{self.imerominia.year}{TEUXOS_KODIKOI[self.teuxos]}{self.arithmos:05d}"

    def anafora(self) -> str:
        """Ανθρώπινη παραπομπή, π.χ. «Α΄100/13-06-2025»."""
        teuxos = TEUXOS_ELLINIKA[self.teuxos]
        return f"{teuxos}΄{self.arithmos}/{self.imerominia:%d-%m-%Y}"


class Pigi(BaseModel):
    typos: TyposPigis
    url: str


class Scheseis(BaseModel):
    """Σχέσεις με άλλα νομοθετήματα του μητρώου."""

    antikathista: list[str] = Field(default_factory=list)
    antikatastathike_apo: list[str] = Field(default_factory=list)
    tropopoiei: list[str] = Field(default_factory=list)
    tropopoieitai_apo: list[str] = Field(default_factory=list)
    kodikopoiei: list[str] = Field(default_factory=list)
    kodikopoiithike_apo: list[str] = Field(default_factory=list)
    ensomatothike_me: list[str] = Field(default_factory=list)

    def oles_oi_anafores(self) -> list[str]:
        return [
            ref
            for pedio in type(self).model_fields
            for ref in getattr(self, pedio)
        ]


class Nomothetima(BaseModel):
    id: str
    titlos: str
    syntomos_titlos: str | None = None
    typos: Typos
    arithmos: str
    etos: int
    fek: Fek | None = None
    celex: str | None = None
    thematiki: str
    proteraiotita: int = Field(ge=1, le=3)
    katastasi: Katastasi
    isxys_apo: dt.date | None = None
    epalithevmeno: bool = False
    perigrafi: str
    relevanta_arthra: list[int] = Field(default_factory=list)
    scheseis: Scheseis = Field(default_factory=Scheseis)
    piges: list[Pigi] = Field(default_factory=list)
    simeioseis: str | None = None

    @model_validator(mode="after")
    def _elegxos_tautotitas(self) -> Nomothetima:
        einai_enosiako = self.typos in (Typos.KANONISMOS_EE, Typos.ODIGIA_EE)
        if einai_enosiako:
            if not self.celex:
                raise ValueError(f"{self.id}: ενωσιακή πράξη χωρίς αριθμό CELEX")
        elif self.fek is None:
            raise ValueError(f"{self.id}: εθνικό νομοθέτημα χωρίς παραπομπή σε ΦΕΚ")
        if not self.piges:
            raise ValueError(f"{self.id}: καμία πηγή λήψης")
        return self

    @property
    def onoma(self) -> str:
        """Σύντομη αναφορά για εμφάνιση, π.χ. «Ν. 5209/2025»."""
        protheme = {
            Typos.NOMOS: "Ν.",
            Typos.PD: "Π.Δ.",
            Typos.YA: "Υ.Α.",
            Typos.KYA: "Κ.Υ.Α.",
            Typos.KANONISMOS_EE: "Καν.",
            Typos.ODIGIA_EE: "Οδηγία",
        }[self.typos]
        if self.typos in (Typos.KANONISMOS_EE, Typos.ODIGIA_EE):
            return f"{protheme} {self.arithmos}"
        return f"{protheme} {self.arithmos}/{self.etos}"

    def fakelos_corpus(self) -> Path:
        return repo_riza() / "corpus" / self.thematiki / self.id


class MetaMitroou(BaseModel):
    ekdosi: int
    enimerosi: dt.date
    perigrafi: str


class Mitroo(BaseModel):
    meta: MetaMitroou
    nomothetimata: list[Nomothetima]

    @model_validator(mode="after")
    def _elegxos_synepeias(self) -> Mitroo:
        ids = [n.id for n in self.nomothetimata]
        diplotypa = {i for i in ids if ids.count(i) > 1}
        if diplotypa:
            raise ValueError(f"διπλά αναγνωριστικά στο μητρώο: {sorted(diplotypa)}")

        gnosta = set(ids)
        for n in self.nomothetimata:
            for ref in n.scheseis.oles_oi_anafores():
                if ref not in gnosta:
                    raise ValueError(
                        f"{n.id}: η σχέση παραπέμπει σε άγνωστο νομοθέτημα {ref!r}"
                    )
        return self

    def get(self, nomothetima_id: str) -> Nomothetima:
        for n in self.nomothetimata:
            if n.id == nomothetima_id:
                return n
        raise KeyError(f"δεν υπάρχει νομοθέτημα με id {nomothetima_id!r}")

    def kata_proteraiotita(self) -> list[Nomothetima]:
        return sorted(self.nomothetimata, key=lambda n: (n.proteraiotita, n.id))

    def thematikes(self) -> list[str]:
        return sorted({n.thematiki for n in self.nomothetimata})


def diadromi_mitroou() -> Path:
    return repo_riza() / "sources" / "registry.yaml"


def fortose_mitroo(diadromi: Path | None = None) -> Mitroo:
    """Διαβάζει και ελέγχει το μητρώο. Σφάλμα σημαίνει άκυρο registry.yaml."""
    diadromi = diadromi or diadromi_mitroou()
    with diadromi.open(encoding="utf-8") as f:
        dedomena = yaml.safe_load(f)
    return Mitroo.model_validate(dedomena)
