# Dementia / cognitive impairment diagnosis checklist

## Cohort definition
- Diagnostic labels and criteria used (e.g. NIA-AA, DSM-5, clinical consensus), who assigned them, blinded to the index test?
- Groups (cognitively normal / SCD / MCI / AD / other dementias) and how MCI subtypes are handled.
- Cognitive scores (MMSE, MoCA, CDR) — if used as inputs they may leak the label; if used as reference, say so.
- Public cohorts commonly used (ADNI, OASIS, NACC, AIBL, etc.) have their own access rules — record the DUA.

## Confounders to control or report
- Age, sex, years of education, vision status (critical for eye tracking), medication, comorbidities, language/culture of tasks, site/device.
- Match groups or adjust (covariates, stratified evaluation); report a demographic-only baseline model.

## Evaluation
- Subject-level splits; longitudinal visits grouped per subject.
- Report AUROC + sensitivity/specificity with 95% CIs; for screening, emphasise sensitivity at acceptable specificity; calibration.
- Subgroup analysis by age band, sex, education, disease stage; class imbalance handled explicitly.
- Spectrum bias: case-control designs inflate accuracy vs. real screening populations — state the intended use setting.
- Follow STARD (diagnostic accuracy) and TRIPOD+AI (prediction models).
