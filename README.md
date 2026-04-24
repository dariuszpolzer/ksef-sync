# ksef-sync

Integracja z KSeF w Pythonie.

Funkcje:
- synchronizacja faktur z KSeF API
- przetwarzanie batchy XML
- generowanie podglądu faktur PDF
- przygotowanie danych do JPK_V7
- indeks HTML faktur

Pipeline:

KSeF API → batch XML → PDF → manifest → JPK

## Diagram działania

```mermaid
flowchart TD
    A[KSeF API] --> B[ksef-sync]

    B --> C[Uwierzytelnienie]
    C --> D[Eksport faktur]

    D --> D1[Subject1: sprzedaż]
    D --> D2[Subject2: zakup / koszty]

    D1 --> E[Pobranie paczek]
    D2 --> E

    E --> F[Odszyfrowanie AES]
    F --> G[Rozpakowanie ZIP]

    G --> H[Batch]

    H --> I[invoices/*.xml]
    H --> J[raw/]
    H --> K[logs/]
    H --> L[manifest.json]

    I --> M[Generator PDF MF]
    M --> N[pdf/*.pdf]

    I --> O[ksef2jpk]
    O --> P[JPK_V7 XML]
    O --> Q[Podgląd HTML JPK]

    H --> R[index.html]
    N --> R
    I --> R