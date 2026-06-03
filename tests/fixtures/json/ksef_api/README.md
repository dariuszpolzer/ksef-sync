Zanonimizowane fixture kontraktowe odpowiedzi API KSeF.

Cel:
- utrzymać oczekiwany kształt odpowiedzi API w testach,
- szybko wykryć zmianę kontraktu MF,
- nie przechowywać prawdziwych tokenów, referencji ani danych faktur.

Pliki `*_response.json` są wejściem dla walidatorów z `ksef.contracts`.
Plik `rate_limit_429.json` opisuje odpowiedź HTTP 429 wraz z wymaganym nagłówkiem.
