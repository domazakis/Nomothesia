"""Γραμμή εντολών του Nomothesia.

    nomothesia validate   έλεγχος του μητρώου (χωρίς δίκτυο)
    nomothesia status     τι υπάρχει και τι λείπει από το corpus
    nomothesia fetch      λήψη και ενημέρωση των κειμένων
    nomothesia changes    τι άλλαξε από την τελευταία λήψη
    nomothesia export     knowledge base για φωνητικό agent
    nomothesia syndesmoi  πού οδηγούν οι σύνδεσμοι μιας σελίδας — ανίχνευση πηγών
    nomothesia keimeno    τι βλέπει ο αγωγός σε μια πηγή — διάγνωση εξαγωγής
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from nomothesia import changes as ch
from nomothesia.export import exagoge_nomothetimatos, gia_knowledge_base
from nomothesia.extract.doc import einai_doc, keimeno_apo_doc
from nomothesia.extract.html import keimeno_apo_html, syndesmoi_apo_html
from nomothesia.extract.pdf import exei_epipedo_keimenou, keimeno_apo_pdf
from nomothesia.fetch.base import Lipsi, SfalmaLipsis
from nomothesia.normalize.greek import kanonikopoiise
from nomothesia.normalize.structure import analyse_domi
from nomothesia.pipeline import SfalmaAgogou, epexergasou
from nomothesia.registry import (
    Katastasi,
    Mitroo,
    Nomothetima,
    fortose_mitroo,
    repo_riza,
)

app = typer.Typer(
    help="Συλλογή και ενημέρωση της ελληνικής νομοθεσίας για την οδήγηση.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _mitroo() -> Mitroo:
    try:
        return fortose_mitroo()
    except Exception as exc:
        console.print(f"[bold red]Άκυρο μητρώο:[/] {exc}")
        raise typer.Exit(code=1) from exc


def _epilogi(
    mitroo: Mitroo, nomothetima_id: str | None, thematiki: str | None
) -> list[Nomothetima]:
    epilegmena = mitroo.kata_proteraiotita()
    if nomothetima_id:
        epilegmena = [n for n in epilegmena if n.id == nomothetima_id]
        if not epilegmena:
            console.print(f"[bold red]Άγνωστο αναγνωριστικό:[/] {nomothetima_id}")
            raise typer.Exit(code=1)
    if thematiki:
        epilegmena = [n for n in epilegmena if n.thematiki == thematiki]
        if not epilegmena:
            console.print(f"[bold red]Άγνωστη θεματική:[/] {thematiki}")
            raise typer.Exit(code=1)
    return epilegmena


@app.command()
def validate() -> None:
    """Ελέγχει ότι το `sources/registry.yaml` είναι έγκυρο και συνεπές."""
    mitroo = _mitroo()

    console.print(
        f"[bold green]✓[/] Το μητρώο είναι έγκυρο — "
        f"{len(mitroo.nomothetimata)} νομοθετήματα σε "
        f"{len(mitroo.thematikes())} θεματικές."
    )

    anepalithefta = [n for n in mitroo.nomothetimata if not n.epalithevmeno]
    if anepalithefta:
        console.print(
            f"\n[yellow]⚠[/]  {len(anepalithefta)} νομοθετήματα με "
            f"ανεπαλήθευτα στοιχεία ΦΕΚ. Θα επαληθευτούν αυτόματα με το "
            f"πρώτο επιτυχές `nomothesia fetch`:"
        )
        for n in anepalithefta:
            console.print(f"    [dim]•[/] {n.id}")

    katargimena = [
        n for n in mitroo.nomothetimata if n.katastasi is not Katastasi.ISXYON
    ]
    if katargimena:
        console.print(
            f"\n[dim]Σημείωση: {len(katargimena)} νομοθετήματα δεν αποτελούν "
            f"ισχύον δίκαιο και σημαίνονται αναλόγως στο corpus.[/]"
        )


@app.command()
def status() -> None:
    """Δείχνει ποια νομοθετήματα υπάρχουν ήδη στο corpus και ποια λείπουν."""
    mitroo = _mitroo()
    manifest = ch.fortose_manifest()

    pinakas = Table(title="Κατάσταση corpus")
    pinakas.add_column("Αναγνωριστικό", style="cyan", no_wrap=True)
    pinakas.add_column("Νομοθέτημα")
    pinakas.add_column("Θεματική", style="dim")
    pinakas.add_column("Προτ.", justify="center")
    pinakas.add_column("Corpus", justify="center")

    plithos_etoimon = 0
    for n in mitroo.kata_proteraiotita():
        yparchei = (n.fakelos_corpus() / "full.md").exists()
        plithos_etoimon += yparchei
        endeixi = "[green]✓[/]" if yparchei else "[red]—[/]"
        if yparchei and n.id in manifest:
            arthra = manifest[n.id].get("plithos_arthron", "?")
            endeixi = f"[green]✓[/] [dim]{arthra} άρθρα[/]"
        pinakas.add_row(
            n.id,
            n.syntomos_titlos or n.onoma,
            n.thematiki,
            str(n.proteraiotita),
            endeixi,
        )

    console.print(pinakas)
    console.print(
        f"\n{plithos_etoimon}/{len(mitroo.nomothetimata)} νομοθετήματα στο corpus."
    )
    if plithos_etoimon < len(mitroo.nomothetimata):
        console.print("[dim]Τρέξε `nomothesia fetch` για να συμπληρωθούν.[/]")


@app.command()
def fetch(
    id: str | None = typer.Option(None, "--id", help="Μόνο ένα νομοθέτημα."),
    thematiki: str | None = typer.Option(None, help="Μόνο μία θεματική."),
    proteraiotita: int | None = typer.Option(
        None, help="Μόνο μέχρι αυτό το επίπεδο προτεραιότητας (1=πυρήνας)."
    ),
    fresh: bool = typer.Option(False, help="Αγνόησε την τοπική προσωρινή μνήμη."),
    verbose: bool = typer.Option(False, "-v", help="Αναλυτική καταγραφή."),
) -> None:
    """Κατεβάζει τα νομοθετήματα και ξαναχτίζει το corpus."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    mitroo = _mitroo()
    epilegmena = _epilogi(mitroo, id, thematiki)
    if proteraiotita is not None:
        epilegmena = [n for n in epilegmena if n.proteraiotita <= proteraiotita]

    palio_manifest = ch.fortose_manifest()
    neo_manifest = dict(palio_manifest)
    epityxies, apotyxies = 0, 0

    with Lipsi() as lipsi:
        for n in epilegmena:
            console.print(f"[cyan]→[/] {n.id} [dim]({n.onoma})[/]")
            try:
                apotelesma = epexergasou(n, lipsi, agnoise_cache=fresh)
            except SfalmaAgogou as exc:
                console.print(f"  [bold red]✗[/] {exc}")
                apotyxies += 1
                continue

            for proeidopoiisi in apotelesma.proeidopoiiseis:
                console.print(f"  [yellow]⚠[/]  {proeidopoiisi}")

            console.print(
                f"  [green]✓[/] {apotelesma.plithos_arthron} άρθρα, "
                f"{apotelesma.plithos_paragrafon} παράγραφοι"
            )
            neo_manifest[n.id] = {
                "checksum_pigis": apotelesma.checksum_pigis,
                "checksum_keimenou": apotelesma.checksum_keimenou,
                "plithos_arthron": apotelesma.plithos_arthron,
                "plithos_paragrafon": apotelesma.plithos_paragrafon,
                "pigi_url": apotelesma.pigi_url,
                "epalithevmeno_fek": apotelesma.epalithevmeno_fek,
            }
            epityxies += 1

    ch.grapse_manifest(neo_manifest)

    allages = ch.ousiastikes(ch.sygkrine(palio_manifest, neo_manifest))
    console.print(f"\n[bold]Ολοκληρώθηκε:[/] {epityxies} επιτυχίες, {apotyxies} αποτυχίες.")
    if allages:
        console.print("\n[bold]Αλλαγές:[/]")
        for a in allages:
            console.print(f"  • {a.perigrafi()}")
    else:
        console.print("[dim]Καμία αλλαγή σε σχέση με την προηγούμενη λήψη.[/]")

    if apotyxies:
        raise typer.Exit(code=1)


@app.command()
def export() -> None:
    """Παράγει το knowledge base για φωνητικό agent, στον φάκελο `export/`.

    Ένα αρχείο ανά νομοθέτημα, κάθε άρθρο με την ταυτότητά του από πάνω και τις
    συντομογραφίες ανοιγμένες για εκφώνηση. Μόνο ισχύον δίκαιο.
    """
    mitroo = _mitroo()
    epilegmena = gia_knowledge_base(mitroo)
    katargimena = len(mitroo.nomothetimata) - len(epilegmena)

    pinakas = Table(title="Knowledge base")
    pinakas.add_column("Νομοθέτημα")
    pinakas.add_column("Άρθρα", justify="right")
    pinakas.add_column("Μέγεθος", justify="right")
    pinakas.add_column("Αρχείο", style="dim")

    apotelesmata = [
        apotelesma
        for n in epilegmena
        if (apotelesma := exagoge_nomothetimatos(n)) is not None
    ]
    for a in apotelesmata:
        pinakas.add_row(
            a.nomothetima_id,
            str(a.plithos_arthron),
            f"{a.charaktires / 1000:.0f}k",
            str(a.diadromi.relative_to(repo_riza())),
        )

    console.print(pinakas)
    console.print(
        f"\n{len(apotelesmata)} αρχεία στο [bold]export/[/] — "
        f"{sum(a.plithos_arthron for a in apotelesmata)} άρθρα."
    )
    if katargimena:
        console.print(
            f"[dim]{katargimena} νομοθετήματα εξαιρέθηκαν ως μη ισχύοντα: ένας "
            f"agent που απαντά με καταργημένη διάταξη δίνει λάθος απάντηση.[/]"
        )
    leipoun = len(epilegmena) - len(apotelesmata)
    if leipoun:
        console.print(
            f"[yellow]⚠[/]  {leipoun} νομοθετήματα λείπουν από το corpus — "
            f"τρέξε `nomothesia fetch`."
        )


def _agnosta_nomothetimata(
    evrethenta: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Κρατά όσα δεν καλύπτονται ήδη από το μητρώο.

    Ο κατάλογος μιας κατηγορίας έχει διακόσιες εγγραφές και το ερώτημα είναι
    «τι μας λείπει». Η σύγκριση γίνεται στον αριθμό και το έτος, όπως
    εμφανίζονται στο κείμενο του συνδέσμου («Νόμος 5209/2025»), ώστε να μην
    εξαρτάται από τη μορφή της διεύθυνσης.

    Τα καταργημένα παραλείπονται: δεν πρόκειται να μπουν στο knowledge base.
    """
    import re

    mitroo = _mitroo()
    gnosta = {
        (str(n.arithmos).strip(), str(n.etos)) for n in mitroo.nomothetimata
    }
    tautotita = re.compile(r"(\d{1,6})\s*/\s*((?:19|20)\d{2})")

    apotelesma = []
    for keimeno, syndesmos in evrethenta:
        if "Καταργη" in keimeno or "καταργη" in keimeno:
            continue
        taires = tautotita.findall(keimeno)
        if any((ar, et) in gnosta for ar, et in taires):
            continue
        apotelesma.append((keimeno, syndesmos))
    return apotelesma


def _morfi(dedomena: bytes) -> str:
    """Τι είναι πραγματικά το αρχείο, ανεξάρτητα από την κατάληξή του.

    Μια διεύθυνση που τελειώνει σε `.doc` μπορεί να κρύβει Word, RTF ή σκέτο
    HTML. Η διαφορά καθορίζει αν διαβάζεται καθόλου, οπότε δεν μαντεύεται από
    το όνομα.
    """
    ypografes = (
        (b"%PDF-", "PDF"),
        (b"\xd0\xcf\x11\xe0", "Word (παλαιό δυαδικό .doc)"),
        (b"PK\x03\x04", "ZIP ή .docx — δεν διαβάζεται ακόμη"),
        (b"{\\rtf", "RTF"),
    )
    for ypografi, onoma in ypografes:
        if dedomena.startswith(ypografi):
            return onoma
    arxi = dedomena[:400].lstrip().lower()
    if arxi.startswith((b"<!doctype", b"<html", b"<?xml")):
        return "HTML ή XML"
    return "άγνωστη"


@app.command()
def keimeno(
    url: str = typer.Argument(..., help="Η σελίδα ή το αρχείο προς εξέταση."),
    grammes: int = typer.Option(40, help="Πόσες γραμμές κειμένου να δείξει."),
) -> None:
    """Δείχνει τι βλέπει ο αγωγός σε μια πηγή — και τι δομή αναγνωρίζει.

    Το «δεν εντοπίστηκε κανένα άρθρο» λέει ότι κάτι πήγε στραβά, όχι τι. Η
    εντολή δείχνει τις πρώτες γραμμές του κανονικοποιημένου κειμένου και πόσα
    άρθρα βρήκε ο parser, ώστε η διαφορά ανάμεσα στο «δεν κατέβηκε» και στο
    «κατέβηκε αλλά γράφεται αλλιώς» να φαίνεται με μια ματιά.
    """
    with Lipsi() as lipsi:
        try:
            apotelesma = lipsi.kateveste(url)
        except SfalmaLipsis as exc:
            console.print(f"[bold red]✗[/] {exc}")
            raise typer.Exit(code=1) from exc

    console.print(f"[dim]μορφή:[/] {_morfi(apotelesma.perieksomeno)}\n")

    if apotelesma.einai_pdf:
        if not exei_epipedo_keimenou(apotelesma.perieksomeno):
            console.print("[bold red]✗[/] σαρωμένο PDF, χωρίς επίπεδο κειμένου")
            raise typer.Exit(code=1)
        akatergasto = keimeno_apo_pdf(apotelesma.perieksomeno)
    elif einai_doc(apotelesma.perieksomeno):
        akatergasto = keimeno_apo_doc(apotelesma.perieksomeno)
    else:
        akatergasto = keimeno_apo_html(apotelesma.perieksomeno)

    kanoniko = kanonikopoiise(akatergasto)
    arthra = analyse_domi(kanoniko)

    console.print(
        f"[bold]{len(apotelesma.perieksomeno)}[/] bytes → "
        f"[bold]{len(kanoniko)}[/] χαρακτήρες → "
        f"[bold]{len(arthra)}[/] άρθρα\n"
    )
    for grammi in kanoniko.split("\n")[:grammes]:
        console.print(f"  {grammi[:100]}")


@app.command()
def syndesmoi(
    url: str = typer.Argument(..., help="Η σελίδα που θα εξεταστεί."),
    filtro: str | None = typer.Option(
        None,
        help="Κράτα όσους συνδέσμους περιέχουν κάποιον από αυτούς τους όρους "
        "(χωρισμένους με κόμμα).",
    ),
    plithos: int = typer.Option(200, help="Μέγιστο πλήθος αποτελεσμάτων."),
    selides: int = typer.Option(
        1, help="Πόσες σελίδες καταλόγου να διατρέξει, μέσω `?page=N`."
    ),
    agnosta: bool = typer.Option(
        False,
        help="Μόνο ό,τι δεν υπάρχει ήδη στο μητρώο και δεν είναι καταργημένο.",
    ),
) -> None:
    """Δείχνει τους συνδέσμους μιας σελίδας — για ανίχνευση νέων πηγών.

    Όταν η επίσημη πηγή δεν κατεβαίνει, το ερώτημα γίνεται «ποια σελίδα έχει
    αυτόν τον νόμο και πού δείχνει». Η εντολή απαντά χωρίς μαντεψιές, και
    τρέχει και μέσα από το GitHub Action για περιβάλλοντα που δεν έχουν τα
    ίδια δικαιώματα δικτύου.

    Με `--selides` διατρέχει και τη σελιδοποίηση ενός καταλόγου, ώστε ο έλεγχος
    «τι υπάρχει εκεί που δεν έχουμε» να μη χρειάζεται μία εκτέλεση ανά σελίδα.
    """
    evrethenta: list[tuple[str, str]] = []
    idonta: set[str] = set()

    with Lipsi() as lipsi:
        for selida in range(1, max(selides, 1) + 1):
            diefthynsi = url if selida == 1 else f"{url.rstrip('/')}/?page={selida}"
            try:
                apotelesma = lipsi.kateveste(diefthynsi)
            except SfalmaLipsis as exc:
                console.print(f"[bold red]✗[/] {exc}")
                if selida == 1:
                    raise typer.Exit(code=1) from exc
                break
            for keimeno, syndesmos in syndesmoi_apo_html(
                apotelesma.perieksomeno, vasi=diefthynsi
            ):
                if syndesmos not in idonta:
                    idonta.add(syndesmos)
                    evrethenta.append((keimeno, syndesmos))

    if filtro:
        oroi = [o.strip().lower() for o in filtro.split(",") if o.strip()]
        evrethenta = [
            (k, u)
            for k, u in evrethenta
            if any(o in u.lower() or o in k.lower() for o in oroi)
        ]

    if agnosta:
        evrethenta = _agnosta_nomothetimata(evrethenta)

    console.print(f"[bold]{len(evrethenta)}[/] σύνδεσμοι από {url}\n")
    for keimeno, syndesmos in evrethenta[:plithos]:
        # Μία γραμμή ανά σύνδεσμο: ο κατάλογος διαβάζεται σε ένα log, όχι σε έξι.
        console.print(f"{syndesmos.rsplit('/', 1)[-1]:<44} {keimeno[:64]}")
    if len(evrethenta) > plithos:
        console.print(f"\n[dim]…και {len(evrethenta) - plithos} ακόμη.[/]")


@app.command()
def changes() -> None:
    """Συγκρίνει το corpus με το manifest και δείχνει τι έχει αλλάξει."""
    mitroo = _mitroo()
    manifest = ch.fortose_manifest()

    if not manifest:
        console.print(
            "[yellow]Δεν υπάρχει ακόμη manifest.[/] Τρέξε πρώτα `nomothesia fetch`."
        )
        raise typer.Exit(code=1)

    leipoun = [n.id for n in mitroo.nomothetimata if n.id not in manifest]
    perissepsan = [nid for nid in manifest if nid not in {n.id for n in mitroo.nomothetimata}]

    console.print(f"Manifest: {len(manifest)} νομοθετήματα.")
    if leipoun:
        console.print("\n[yellow]Στο μητρώο αλλά όχι στο corpus:[/]")
        for nid in leipoun:
            console.print(f"  • {nid}")
    if perissepsan:
        console.print("\n[yellow]Στο corpus αλλά όχι στο μητρώο:[/]")
        for nid in perissepsan:
            console.print(f"  • {nid}")
    if not leipoun and not perissepsan:
        console.print("[green]✓[/] Το corpus συμφωνεί με το μητρώο.")


if __name__ == "__main__":
    app()
