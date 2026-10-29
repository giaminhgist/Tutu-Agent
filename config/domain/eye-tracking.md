# Eye-tracking research checklist

## Acquisition & metadata (record in the dataset registry / methods)
- Device model, sampling rate (Hz), tracking mode (monocular/binocular), head stabilisation (chin rest / remote / head-mounted / VR / webcam).
- Calibration: method (5/9-point), validation accuracy & precision (deg visual angle) per session; exclusion threshold set *before* analysis.
- Screen geometry: size, resolution, viewing distance -> pixels-per-degree conversion.
- Task paradigm (free viewing, visual search, reading, pro/anti-saccade, smooth pursuit, VPC/novelty preference) and stimulus timing.
- Prefer BIDS (eye-tracking/physio extension) or a documented tabular schema; keep raw vendor files (EDF/ASC/IDF/TSV) read-only.

## Preprocessing
- Track loss / blinks: detect, pad (e.g. ±50–100 ms), interpolate only short gaps; report % data loss per participant and per class.
- Event detection: name the algorithm and parameters (I-VT velocity threshold, I-DT dispersion/duration, or ML-based), report them; same parameters across groups.
- Filtering/smoothing parameters; coordinate range checks; drift correction policy.
- Apply data-quality exclusion identically across diagnostic groups (differential exclusion is a confounder).

## Features & models
- Classical: fixation count/duration, saccade amplitude/velocity/latency, regressions, pupil (with luminance control), AOI dwell/transition entropy, scanpath similarity (ScanMatch, MultiMatch).
- Learned: scanpath sequence models, gaze heatmaps over stimuli, multimodal (gaze + image/text). Keep a classical-feature baseline.

## Evaluation pitfalls
- Split at **participant** level (never trial/session level). Group-k-fold by subject ID.
- Report per-participant aggregation strategy if predicting per trial.
- Check that models are not learning calibration quality, device, or session order.
