# Medical imaging AI checklist

## Data governance
- De-identification: DICOM header PHI tags removed/hashed, burned-in annotations checked, face-removal (defacing) for head MRI/CT when sharing.
- Record source, licence / DUA, IRB approval, consent scope; never upload project data to external services without approval.
- Keep raw DICOM/NIfTI read-only (`data.protected_paths`); derived volumes elsewhere with the preprocessing script + version.

## Preprocessing (document every step)
- Orientation (RAS/LPS), voxel spacing & resampling, intensity normalisation (z-score / histogram matching / bias-field correction N4), skull stripping, registration template (e.g. MNI) and tool versions.
- For retinal imaging (fundus/OCT): device, field of view, quality grading and exclusion criteria.

## Splits & validation
- **Patient-level** splits; no slices/patches/visits of one patient across splits; longitudinal scans grouped by patient.
- Site/scanner effects: report per-site results; consider leave-one-site-out; harmonisation (ComBat) fitted on train only.
- External validation set whenever possible; otherwise state as limitation.

## Metrics & reporting
- Classification: AUROC (95% CI), sensitivity/specificity at a pre-specified threshold, PPV/NPV with prevalence, calibration.
- Segmentation: Dice + a boundary metric (HD95/ASSD), per-structure, with CIs; inter-rater variability as a reference ceiling.
- Explainability maps (Grad-CAM etc.) are qualitative; sanity-check them (randomisation tests) before interpreting.
- Follow CLAIM (imaging AI) and, for prediction models, TRIPOD+AI.
