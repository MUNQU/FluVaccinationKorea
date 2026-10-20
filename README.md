# FluVaccinationKorea

Influenza and influenza vaccination data for South Korea, in one common format. The goal is
to repeat the analysis of `FluVaccinationLoRegne` (Valencian Community, Spain) with Korean
data and to compare the results.

- Sources and coverage: [docs/data-sources.md](docs/data-sources.md)
- Inputs of the first model (2016-2017, 65+): [docs/model-inputs.md](docs/model-inputs.md)
- File format: [docs/data-format.md](docs/data-format.md)
- One page per source: [docs/sources/](docs/sources/)

## Layout

```
data/raw/        original downloaded files (one folder per source)
data/processed/  files in the common format
scripts/         download and processing (common.py defines the format)
docs/            documentation
drafts/          starting notes and data shared by Dr. Son (drafts/data/)
```

## Acknowledgements

- Dr. Woo-Sik Son ([woosikson](https://github.com/woosikson)) shared an independent build of
  the KDCA sentinel ILI, SARI and influenza positivity series (`drafts/data/`, codebook
  `drafts/DICTIONARY.md`). We used it to cross-check our extraction; see
  [docs/sources/kdca_sentinel.md](docs/sources/kdca_sentinel.md). The contact matrices come
  from the repository
  [woosikson/age-rt-smoother](https://github.com/woosikson/age-rt-smoother) (Kim, Kim and
  Son); see [docs/sources/contact_matrices.md](docs/sources/contact_matrices.md).
