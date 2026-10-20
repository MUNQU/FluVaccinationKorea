# FluVaccinationKorea

Influenza and influenza vaccination data for South Korea, in one common format. The goal is
to repeat the analysis of `FluVaccinationLoRegne` (Valencian Community, Spain) with Korean
data and to compare the results.

- Sources and coverage: [docs/data-sources.md](docs/data-sources.md)
- File format: [docs/data-format.md](docs/data-format.md)
- One page per source: [docs/sources/](docs/sources/)

## Layout

```
data/raw/        original downloaded files (one folder per source)
data/processed/  files in the common format
scripts/         download and processing (common.py defines the format)
docs/            documentation
drafts/          starting notes
```
