# ksef-sync production runbook

## Kontrola przed uruchomieniem

Uruchom z katalogu glownego repozytorium:

```powershell
uv sync --extra dev
uv run python -m pytest
uv run python -m ruff check .
uv run python -m black --check main.py config.py ksef tests
uv run python -m bandit -q -c pyproject.toml -r .
```

Sprawdz `.env` przed kazdym uruchomieniem produkcyjnym:

- `KSEF_NIP` wskazuje wlasciwy kontekst podatnika.
- `KSEF_TOKEN` jest aktualny i ma wymagane uprawnienia.
- `KSEF_PUBLIC_KEY_PATH` oraz `KSEF_SYMMETRIC_KEY_CERT_PATH` wskazuja istniejace pliki.
- `KSEF_DATA_DIR`, `KSEF_BATCH_DIR`, `KSEF_EXPORT_DIR` i `KSEF_LOG_DIR` wskazuja docelowe katalogi produkcyjne.

## Synchronizacja miesieczna

```powershell
uv run python main.py --mode full-sync --year 2026 --month 4
```

Artefakty:

- XML/PDF/index batcha: `data/batches/<batch_id>/`
- diagnostyka auth/export: `data/auth/`, `data/exports/`
- logi aplikacji: `data/logs/`

Po synchronizacji zwaliduj batch:

```powershell
uv run python main.py --mode validate-batch --batch-id <batch_id>
```

Bez `--batch-id` walidowany jest najnowszy batch:

```powershell
uv run python main.py --mode validate-batch
```

Walidacja tworzy `validation_report.json` w katalogu batcha i zapisuje hashe SHA-256 plikow XML oraz PDF.

## Orchestrator

`orchestrator.ps1` moze uruchomic caly lokalny proces miesieczny:

```powershell
.\orchestrator.ps1 -Year 2026 -Month 4
```

Domyslnie skrypt:

- traktuje katalog, w ktorym lezy `orchestrator.ps1`, jako `ksef-sync`,
- traktuje katalog nadrzedny jako root dla `ksef-jpk`, `tax-app`, `logs` i `reports`.

Sciezki mozna nadpisac parametrami:

```powershell
.\orchestrator.ps1 `
  -Year 2026 `
  -Month 4 `
  -RootDir "D:\Accounting" `
  -Ksef2JpkDir "D:\Accounting\ksef-jpk" `
  -TaxAppDir "D:\Accounting\tax-app"
```

Jesli `-BatchDir` nie jest podany, skrypt wybiera najnowszy batch z `ksef-sync\data\batches`.
Ten batch jest walidowany przez `ksef-sync`, a nastepnie przekazywany do `ksef-jpk` jako `--batch-dir`.

Mozna tez wymusic konkretny batch:

```powershell
.\orchestrator.ps1 -Year 2026 -Month 4 -BatchDir "D:\Accounting\ksef-sync\data\batches\20260521T043024Z"
```

Przed realnym uruchomieniem warto wykonac:

```powershell
.\orchestrator.ps1 -Year 2026 -Month 4 -DryRun
```

## Synchronizacja przyrostowa

```powershell
uv run python main.py --mode incremental
```

Stan synchronizacji przyrostowej jest zapisany w `data/state.json`. Proces uzywa malego okna nakladania zakresu, aby ograniczyc ryzyko pominiecia pozno dostepnych rekordow.

## Obsluga awarii

1. Sprawdz najnowszy plik w `data/logs/`.
2. Jesli powstal batch, sprawdz `data/batches/<batch_id>/manifest.json`.
3. Ponow uruchomienie tego samego okresu dopiero po ustaleniu, czy poprzedni batch zawiera uzywalne faktury.
4. Zachowaj katalogi nieudanych batchy do czasu wyjasnienia bledu; zawieraja surowy slad audytowy.

## Dane wrazliwe

Traktuj `data/`, `keys/`, `.env`, wygenerowane ZIP, XML faktur, PDF i manifesty jako wrazliwe dane ksiegowe. Nie commituj ich. Repozytorium `.gitignore` domyslnie wyklucza te sciezki.

## Retencja batchy

Lista batchy:

```powershell
uv run python main.py --mode list-batches
```

Bezpieczny dry-run cleanupu:

```powershell
uv run python main.py --mode cleanup --older-than-days 90
```

Rzeczywiste usuniecie wymaga jawnego `--execute`:

```powershell
uv run python main.py --mode cleanup --older-than-days 90 --execute
```

Cleanup usuwa tylko katalogi znajdujace sie pod `KSEF_BATCH_DIR`.
