"""Γραμμή εντολών του Nomothesia.

    nomothesia validate   έλεγχος του μητρώου (χωρίς δίκτυο)
    nomothesia status     τι υπάρχει και τι λείπει από το corpus
    nomothesia fetch      λήψη και ενημέρωση των κειμένων
    nomothesia changes    τι άλλαξε από την τελευταία λήψη
    nomothesia export     knowledge base για φωνητικό agent
    nomothesia syndesmoi  πού οδηγούν οι σύνδεσμοι μιας σελίδας — ανίχνευση πηγών
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from nomothesia import changes as ch
from nomothesia.export import exagoge_nomothetimatos, gia_knowledge_base
from nomothesia.extract.html import syndesmoi_apo_html
from nomothesia.fetch.base import Lipsi, SfalmaLipsis
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


@app.command()
def syndesmoi(
    url: str = typer.Argument(..., help="Η σελίδα που θα εξεταστεί."),
    filtro: str | None = typer.Option(
        None,
        help="Κράτα όσους συνδέσμους περιέχουν κάποιον από αυτούς τους όρους "
        "(χωρισμένους με κόμμα).",
    ),
    plithos: int = typer.Option(80, help="Μέγιστο πλήθος αποτελεσμάτων."),
) -> None:
    """Δείχνει τους συνδέσμους μιας σελίδας — για ανίχνευση νέων πηγών.

    Όταν η επίσημη πηγή δεν κατεβαίνει, το ερώτημα γίνεται «ποια σελίδα έχει
    αυτόν τον νόμο και πού δείχνει». Η εντολή απαντά χωρίς μαντεψιές, και
    τρέχει και μέσα από το GitHub Action για περιβάλλοντα που δεν έχουν τα
    ίδια δικαιώματα δικτύου.
    """
    with Lipsi() as lipsi:
        try:
            apotelesma = lipsi.kateveste(url)
        except SfalmaLipsis as exc:
            console.print(f"[bold red]✗[/] {exc}")
            raise typer.Exit(code=1) from exc

    evrethenta = syndesmoi_apo_html(apotelesma.perieksomeno, vasi=url)
    if filtro:
        oroi = [o.strip().lower() for o in filtro.split(",") if o.strip()]
        evrethenta = [
            (k, u)
            for k, u in evrethenta
            if any(o in u.lower() or o in k.lower() for o in oroi)
        ]

    console.print(f"[bold]{len(evrethenta)}[/] σύνδεσμοι από {url}\n")
    for keimeno, syndesmos in evrethenta[:plithos]:
        console.print(f"  {keimeno[:70] or '—'}\n    [dim]{syndesmos}[/]")
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
