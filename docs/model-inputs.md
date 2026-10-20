# Model inputs for the 2016-2017 season (65+)

This page collects the inputs that the first model version needs and that do not come
directly from one processed file. The model is the `FluVaccinationLoRegne` model reduced to
the Korean data: age (<65, 65+) × vaccination status (65+ only), no comorbidity strata,
calibrated to the weekly NHIS inpatient episodes of the 65+ group.

## Vaccination of the 65+ group

Source: [nip_vaccination.md](sources/nip_vaccination.md).

| Item | Value | Source |
|---|---|---|
| Target population 65+ | 6,944,490 | NIP registry (data.go.kr 15142108) |
| Final coverage 65+ | 82.8% (5,748,445 persons) | NIP registry |
| Start of the campaign | 4 Oct 2016 (75+), 10 Oct 2016 (65-74) | Seoul Shinmun, 2016-09-22, reporting the KCDC plan (<https://www.seoul.co.kr/news/society/health-medical/2016/09/22/20160922002010>) |
| Vaccinated, 4-8 Oct (W41) | 2,263,357 | KCDC press release |
| Vaccinated, 9-15 Oct (W42) | 2,565,769 | KCDC press release |
| Vaccinated, 16-22 Oct (W43) | 485,686 | KCDC press release |
| Vaccinated, 23-27 Oct (W44, Sun-Thu) | 158,675 | KCDC press release |
| Vaccinated after 27 Oct | 5,748,445 − 5,473,487 = 274,958 (4.0% of 65+) | Difference of the two sources |

The weekly series after 27 October must be built by assumption. The press release asks
the persons not yet vaccinated to get the vaccine in November, before the epidemic. A
simple choice is to spread the remaining ~275,000 persons over the rest of W44 to W48
(end of November), with a decreasing weekly number.

Note: the sum of the four press-release periods is 5,473,487. The release prints a total of
5,473,865 (378 more). The source of this small difference is not known.

## Vaccine effectiveness (VE), 65+, 2016-2017

The 2016-2017 season in Korea was dominated by A(H3N2). The NHIS data cannot identify VE
(no admissions by vaccination status), so the model must fix it.

| Estimate | VE (95% CI) | Outcome and design | Reference |
|---|---|---|---|
| Korea, interim | 4.3% (−137.8 to 61.5) | A(H3N2); ILI patients in emergency rooms and inpatients, tertiary hospitals; test-negative; 1 Sep 2016 – 7 Jan 2017 | Noh JY et al. PLoS One 2017;12(5):e0178010. doi:10.1371/journal.pone.0178010 |
| Korea, end of season | 47.7% (22.6 to 64.7) | Influenza in ILI patients, 10 medical centres; test-negative; subtype not given in the abstract | Choi WS et al. Vaccine 2024. doi:10.1016/j.vaccine.2024.126381 (PMID 39362009) |
| Korea, pooled | 48.4% (29.6 to 62.2) | Influenza-related hospitalization, all A(H3N2)-dominant seasons 2011-2021 (not 2016-2017 alone) | Choi WS et al. Vaccine 2024 (same) |
| Europe (I-MOVE+) | 17% (1 to 31) | Hospitalized SARI, A(H3N2), ≥65; test-negative | Rondy M et al. Euro Surveill 2017;22(41). doi:10.2807/1560-7917.ES.2017.22.41.17-00645 |
| United States | 21% (−15 to 45) | Outpatient ARI, A(H3N2), ≥65; test-negative | Flannery B et al. Clin Infect Dis 2019. doi:10.1093/cid/ciy775 |

The Korean estimates disagree. The interim estimate has a very wide interval. The
end-of-season estimate probably includes influenza B (the abstract does not give the
subtype). Recommendation: use VE = 20% as the central value and run a sensitivity analysis
from 0% to 48%.

Only the two Korean abstracts were read for this page (PMC full text for Noh et al.; Europe
PMC abstract for Choi et al.). The international values come from a literature search and
were not checked again.

## Population

Source: [mois.md](sources/mois.md). Use the population on 31-12-2016 (`season=2016-2017`),
summed by single year of age into <65 and 65+.
