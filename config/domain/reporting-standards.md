# Reporting standards — which one applies

| Study type | Guideline | Notes |
|---|---|---|
| Prediction model (diagnostic/prognostic) using ML/AI | **TRIPOD+AI** | development and/or validation of prediction models |
| AI on medical images | **CLAIM** | checklist for AI in medical imaging |
| Diagnostic accuracy study | **STARD** | index test vs. reference standard |
| Randomised trial of an AI intervention | **CONSORT-AI** / protocol: **SPIRIT-AI** | |
| Early-stage clinical evaluation of AI decision support | **DECIDE-AI** | |
| Risk of bias assessment of prediction models (for reviews) | **PROBAST(+AI)** | used by reviewer agent when appraising literature |

How Tutu uses them
- Methodology agent maps each planned experiment to checklist items.
- Writing agent fills the checklist as a supplementary table (item → section/page).
- Reviewer agent flags missing items as MAJOR (CRITICAL if it hides leakage/bias).

Always fetch the current official checklist (EQUATOR Network) before submission; do not reproduce items from memory as authoritative.
