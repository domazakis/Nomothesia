"""Παρακολούθηση αλλαγών στο corpus.

Η νομοθεσία αλλάζει και αυτό είναι το κύριο πρόβλημα που λύνει το project. Το
`MANIFEST.json` κρατά το αποτύπωμα κάθε νομοθετήματος· η σύγκριση με την
προηγούμενη εκτέλεση δείχνει τι κινήθηκε.

Επειδή το corpus είναι μέσα στο git, η ίδια η αλλαγή είναι ορατή και ως diff —
το manifest απαντά στο «τι άλλαξε», το git στο «πώς ακριβώς».
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from nomothesia.registry import repo_riza


class EidosAllagis(StrEnum):
    NEO = "νέο"
    TROPOPOIIMENO = "τροποποιημένο"
    ACHANGE = "αμετάβλητο"
    APON = "απόν"


@dataclass
class Allagi:
    nomothetima_id: str
    eidos: EidosAllagis
    palio_checksum: str | None = None
    neo_checksum: str | None = None

    def perigrafi(self) -> str:
        return f"{self.nomothetima_id}: {self.eidos.value}"


def diadromi_manifest() -> Path:
    return repo_riza() / "corpus" / "MANIFEST.json"


def checksum_arxeiou(diadromi: Path) -> str:
    return hashlib.sha256(diadromi.read_bytes()).hexdigest()


def fortose_manifest(diadromi: Path | None = None) -> dict[str, dict]:
    diadromi = diadromi or diadromi_manifest()
    if not diadromi.exists():
        return {}
    dedomena = json.loads(diadromi.read_text(encoding="utf-8"))
    return dedomena.get("nomothetimata", {})


def grapse_manifest(
    eggrafes: dict[str, dict], diadromi: Path | None = None
) -> Path:
    diadromi = diadromi or diadromi_manifest()
    diadromi.parent.mkdir(parents=True, exist_ok=True)
    diadromi.write_text(
        json.dumps(
            {
                "enimerosi": dt.date.today().isoformat(),
                "plithos": len(eggrafes),
                "nomothetimata": dict(sorted(eggrafes.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return diadromi


def sygkrine(
    palio: dict[str, dict], neo: dict[str, dict]
) -> list[Allagi]:
    """Συγκρίνει δύο manifests και επιστρέφει τις διαφορές."""
    allages: list[Allagi] = []

    for nid, eggrafi in sorted(neo.items()):
        neo_cs = eggrafi.get("checksum_keimenou")
        if nid not in palio:
            allages.append(Allagi(nid, EidosAllagis.NEO, neo_checksum=neo_cs))
            continue
        palio_cs = palio[nid].get("checksum_keimenou")
        eidos = (
            EidosAllagis.ACHANGE if palio_cs == neo_cs else EidosAllagis.TROPOPOIIMENO
        )
        allages.append(Allagi(nid, eidos, palio_cs, neo_cs))

    for nid in sorted(set(palio) - set(neo)):
        allages.append(
            Allagi(nid, EidosAllagis.APON, palio_checksum=palio[nid].get("checksum_keimenou"))
        )

    return allages


def ousiastikes(allages: list[Allagi]) -> list[Allagi]:
    """Μόνο όσες αξίζει να αναφερθούν — τα αμετάβλητα δεν είναι είδηση."""
    return [a for a in allages if a.eidos is not EidosAllagis.ACHANGE]
