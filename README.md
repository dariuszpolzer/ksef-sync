![Python](https://img.shields.io/badge/python-3.13-blue)
![Quality](https://github.com/dariuszpolzer/ksef-sync/actions/workflows/quality.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-pytest-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

# ksef-sync
## Spis treści

- [Status projektu](#status-projektu)
- [Funkcje](#funkcje)
- [Pipeline](#pipeline)
- [Architektura projektu](#architektura-projektu)
- [Logika okresu JPK](#logika-okresu-jpk)
- [Obsługa NrKSeF](#obsługa-nrksef)
- [GTU](#gtu)
- [Procedury VAT](#procedury-vat)
- [Faktury korygujące](#faktury-korygujące)
- [Deduplikacja](#deduplikacja)
- [Walidacja](#walidacja)
- [Raporty jakości](#raporty-jakości)
- [Bezpieczeństwo](#bezpieczeństwo)
- [Uwagi dotyczące obliczeń finansowych](#uwagi-dotyczące-obliczeń-finansowych)
- [Znane ograniczenia](#znane-ograniczenia)
- [Development](#development)
- [Quick start](#quick-start)
- [Przykładowe uruchomienie](#przykładowe-uruchomienie)
- [Przykładowy workflow](#przykładowy-workflow)
- [Typowe zastosowania](#typowe-zastosowania)
- [Disclaimer](#disclaimer)
- [CI/CD](#cicd)
- [Production](#production)
- [Licencja](#licencja)
- [Autor](#autor)

`ksef-sync` to narzędzie w Pythonie do lokalnej synchronizacji faktur z KSeF, obsługi batchy XML, generowania podglądów PDF oraz przygotowania danych do dalszego przetwarzania, w szczególności pod kątem JPK_V7.

> Lokalny pipeline ETL dla KSeF
>KSeF API → ZIP → XML → PDF → manifest → index.html → JPK_V7
Projekt wspiera proces:

```text
KSeF API → ZIP → XML → PDF → manifest → index.html → JPK_V7
```


## Status projektu

Projekt rozwijany aktywnie.


## Wymagania

- Python 3.13 +
- uv
- Node.js 20+
- PowerShell 7+ (Windows recommended)
- dostęp do środowiska KSeF

## Pipeline

```
KSeF API → ZIP → XML → PDF → manifest → index.html → JPK_V7
```


## Funkcje

* przyrostowa synchronizacja faktur sprzedaży i zakupu z KSeF API
* obsługa uwierzytelnienia i sesji KSeF
* pobieranie, odszyfrowywanie i rozpakowywanie paczek KSeF
* przetwarzanie batchy XML faktur
* generowanie podglądu faktur PDF
* budowanie indeksu HTML dla batchy faktur
* eksport danych do struktur JPK_V7
* generowanie manifestów batchy i metadanych eksportu
* obsługa logów, retry oraz walidacji pobranych danych
* automatyczne testy, linting i kontrola jakości kodu


## Diagram działania

```mermaid
flowchart TD
    A[KSeF API] --> B[ksef-sync]

    B --> C[Uwierzytelnienie i sesja]
    C --> D[Zapytania eksportowe]

    D --> D1[Faktury sprzedaży]
    D --> D2[Faktury zakupu / kosztowe]

    D1 --> E[Pobranie paczek eksportowych]
    D2 --> E

    E --> F[Odszyfrowanie AES]
    F --> G[Rozpakowanie ZIP]

    G --> H[Batch eksportu]

    H --> I[invoices/*.xml]
    H --> J[raw/*.zip]
    H --> K[logs/]
    H --> L[manifest.json]
    H --> M[index.html]

    I --> N[Generator PDF]
    N --> O[pdf/*.pdf]

    I --> P[ksef-sync]
    P --> Q[JPK_V7 XML]
    P --> R[Podgląd HTML JPK]

    O --> M
    I --> M
    Q --> S[Import do systemów księgowych]
```

## Miejsce projektu w procesie rozliczeniowym

`ksef-sync` jest pierwszym ogniwem lokalnego procesu obsługi danych z KSeF.

Jego zadaniem jest pobranie kompletnego zestawu faktur z systemu KSeF za wskazany okres oraz przygotowanie ich do dalszego przetwarzania.

W szerszym workflow projekt może być uruchamiany przez zewnętrzny skrypt orkiestrujący, który wykonuje kolejne etapy procesu miesięcznego:

```text
KSeF
  ↓
ksef-sync
  ↓
XML faktur
  ↓
ksef2jpk
  ↓
pliki JPK
  ↓
tax-app / raporty podatkowe
```
## Orchestrator

Przykładowy miesięczny orchestrator może wykonywać kolejno:

1. synchronizację faktur z KSeF,
2. wygenerowanie struktur JPK w aplikacji `ksef2jpk`,
3. przygotowanie raportów podatkowych w aplikacji `tax-app`,
4. zapis logów i raportów dla danego okresu rozliczeniowego.

Orchestrator używa lokalnych virtual environment (`.venv`)
dla każdego projektu, co zapewnia:
- izolację zależności,
- powtarzalność środowiska uruchomieniowego,
- niezależność od globalnej instalacji Pythona.

### Przykładowe uruchomienie

```powershell
.\orchestrator.ps1 -Year 2026 -Month 4

```
Dostępne przełączniki Orchestrator:

```powershell
-RootDir
-KsefSyncDir
-Ksef2JpkDir
-TaxAppDir
-LogDir
-ReportRootDir
-BatchDir
-SkipBatchValidation
-DryRun
-SkipSync
-SkipJpk
-SkipTaxApp
```
Domyślnie `orchestrator.ps1` traktuje katalog skryptu jako katalog `ksef-sync`,
a katalog nadrzędny jako root dla `ksef-jpk`, `tax-app`, `logs` i `reports`.
Jeśli `-BatchDir` nie jest podany, skrypt wybiera najnowszy batch z `ksef-sync\data\batches`
i przekazuje go do `ksef-jpk` przez `--batch-dir`.
Orchestrator nie jest wymagany do działania `ksef-sync`, ale pokazuje docelowe miejsce projektu w kompletnym, lokalnym procesie rozliczeniowym.

## Instalacja Windows

### Klonowanie repozytorium
```bash
git clone https://github.com/dpolz/ksef-sync.git
cd ksef-sync
```
## Środowisko Python

Projekt używa `uv`. Źródłem prawdy dla zależności jest `pyproject.toml`, a zablokowane wersje są w `uv.lock`.

```bash
uv sync --extra dev
```
### Generator PDF KSeF (Node.js)

Instalacja zależności Node.js:

```bash
cd pdf_generator
npm install
npm run build
```

## Instalacja na Linux

### Klonowanie repozytorium
```bash
git clone https://github.com/dpolz/ksef-sync.git
cd ksef-sync
```
Środowisko Python

```bash
uv sync --extra dev
```
Uruchomienie
```bash
uv run python main.py --mode full-sync --year 2026 --month 5
```
## Konfiguracja

Utwórz plik `.env` na podstawie `.env.example`.

Przykład:
```
KSEF_ENV=demo
KSEF_NIP=0000000000
KSEF_TOKEN=your-token
```
### Konfiguracja `.env`

| Zmienna | Opis |
|---|---|
| `KSEF_ENV` | środowisko (`demo` / `prod`) |
| `KSEF_NIP` | NIP podatnika |
| `KSEF_TOKEN` | token autoryzacyjny |

## 🛡️ Bezpieczeństwo

> [!WARNING]
> Projekt nie wysyła danych do zewnętrznych usług.
> Całość przetwarzania odbywa się lokalnie.
> Dane autoryzacyjne KSeF powinny być przechowywane wyłącznie
> w lokalnym pliku `.env`, który nie jest commitowany do repozytorium.
> Pliki `.env`, batch exportów, logi oraz wygenerowane dane
> są domyślnie wykluczone przez `.gitignore`.

## Uruchomienie

### Synchronizacja przyrostowa (domyślnie)

```bash
uv run python main.py
```

Domyślnie projekt pobiera faktury z ostatnich 7 dni
i zapisuje stan synchronizacji w `data/state.json`.

### Synchronizacja pełna dla wybranego okresu

```bash
uv run python main.py --mode full-sync --year 2026 --month 5
```

### Bezpośrednie uruchomienie modułu

Projekt może działać:
- w trybie manualnym,
- w trybie orchestratora miesięcznego,
- w trybie synchronizacji przyrostowej.

## Przykładowe uruchomienie
### Tryb manualny / diagnostyczny

```text
...\ksef-sync> uv run python main.py

Okres: YYYY-MM
Tryb: menu

=== TRYB MANUALNY / DIAGNOSTYCZNY ===

[KSeF API]
1 - test uwierzytelnienia KSeF
2 - test eksportu/statusu (bez pobierania)
3 - pełny sync testowy (mały zakres)

[OFFLINE / LOKALNIE]
4 - generowanie PDF dla istniejącego batcha
5 - budowa index.html dla batcha

6 - wyjście
```
## Tryby offline

Opcje:
- generowanie PDF,
- budowa index.html

działają całkowicie lokalnie na istniejących batchach XML
i nie angażują API KSeF.

Pozwala to:
- regenerować PDF,
- przebudowywać indeks HTML,
- testować pipeline,
- debugować batch eksportu,

bez ponownego pobierania danych z KSeF.

## Integracja z zewnętrznym orchestratoriem

Projekt może działać jako element większego procesu ETL / księgowego.

Przykładowy orchestrator może wykonywać:

1. synchronizację faktur z KSeF,
2. generowanie batchy XML,
3. generowanie PDF,
4. budowę indeksu HTML,
5. eksport danych do JPK_V7,
6. raportowanie miesięczne.


Projekt został zaprojektowany tak, aby można go było łatwo integrować z:
- harmonogramami Windows Task Scheduler,
- cron,
- GitHub Actions,
- pipeline ETL,
- systemami księgowymi i raportowymi.

## Przykładowe uruchomienie

### Tryb manualny / diagnostyczny

```text
...\ksef-sync> uv run python main.py

Okres: YYYY-MM
Tryb: menu

=== TRYB MANUALNY / DIAGNOSTYCZNY ===

[KSeF API]
1 - test uwierzytelnienia KSeF
2 - test eksportu/statusu (bez pobierania)
3 - pełny sync testowy (mały zakres)

[OFFLINE / LOKALNIE]
4 - generowanie PDF dla istniejącego batcha
5 - budowa index.html dla batcha

6 - wyjście
```

## Limity API KSeF

Projekt respektuje odpowiedzi HTTP 429 (`Too Many Requests`)
oraz nagłówek `Retry-After`.

Dla większych zakresów dat zalecane jest:
- używanie orchestratora,
- synchronizacja przyrostowa,
- ograniczanie zakresu manualnych testów.


## Roadmap

- [x] synchronizacja KSeF
- [x] batch XML
- [x] PDF generator
- [x] HTML indeks
- [x] JPK_V7 export
- [ ] OCR załączników
- [ ] dashboard webowy
- [ ] Docker deployment
- [ ] PostgreSQL backend
- [ ] multi-company support

## Struktura batcha
Batch stanowi trwały artefakt pipeline i może być ponownie używany
bez angażowania API KSeF.
i może być ponownie użyty do:
- regeneracji PDF,
- budowy index.html,
- dalszego eksportu do JPK,
- analizy/debugowania pipeline.
Po wykonaniu pipeline powstają:
```
data/batches/
 ├─ raw/                 # oryginalne paczki ZIP
 ├─ invoices/            # XML faktur
 ├─ pdf/                 # podglądy PDF
 ├─ logs/                # logi przetwarzania
 ├─ manifest.json        # manifest batcha
 └─ index.html           # indeks HTML faktur
```

### Wynik

* XML faktur z KSeF
* PDF podgląd faktur
* manifest batch
* dane do JPK_V7
* HTML indeks faktur

## Testy

Uruchomienie testów:

```bash
uv run pytest
```

Coverage:

```bash
uv run pytest --cov=ksef --cov-report=term-missing
```

## Kontrola jakości

```bash
uv run ruff check .
uv run black --check main.py config.py ksef tests
uv run bandit -q -c pyproject.toml -r .
```

## CI/CD

Kontrole jakości można uruchomić lokalnie:

```powershell
.\check.ps1
```

Repozytorium zawiera też workflow GitHub Actions w `.github/workflows/quality.yml`, który uruchamia testy, ruff, black oraz bandit.

Przed pushem sprawdź:
- `.\check.ps1` kończy się statusem OK,
- `git status` nie pokazuje danych wygenerowanych lub lokalnych,
- w repo nie ma plików z `.env`, `data/`, `keys/`, `logs/`, `exports/` ani batchami roboczymi.

Projekt wykorzystuje GitHub Actions do:
- uruchamiania testów,
- lintingu,
- kontroli jakości kodu.

## Production

Procedura uruchomień produkcyjnych, lista kontroli przed startem oraz obsługa błędów są opisane w [PRODUCTION.md](PRODUCTION.md).

Po synchronizacji batch można sprawdzić lokalnie:

```powershell
uv run python main.py --mode validate-batch --batch-id <batch_id>
```

Batchami można zarządzać lokalnie:

```powershell
uv run python main.py --mode list-batches
uv run python main.py --mode cleanup --older-than-days 90
```

## Licencja

Projekt jest udostępniany na licencji MIT.

Możesz używać, modyfikować i rozpowszechniać projekt również komercyjnie,
pod warunkiem zachowania informacji o autorze i treści licencji.

Szczegółowe warunki znajdują się w pliku `LICENSE`.

## Autor

Dariusz Polzer
