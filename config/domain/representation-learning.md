# Representation learning checklist

- Pretraining data: source, size, overlap with downstream test sets (check for contamination, especially public medical datasets reused across benchmarks).
- Evaluation protocols: linear probe (frozen), kNN, fine-tuning, few-shot (1/5/10/… % labels) curves, out-of-distribution / cross-site transfer.
- Baselines: supervised from scratch, ImageNet-pretrained, a public foundation model of the domain, and random-init encoder for probing sanity.
- Ablations: augmentations, objective terms, encoder size, pretraining data size.
- Fair comparison: same backbone, data budget and tuning budget; report seeds and CIs.
- Embedding analysis: UMAP/t-SNE are qualitative (state hyperparameters); prefer quantitative probes (linear separability, CKA, retrieval mAP), and check that embeddings do not primarily encode site/scanner/device.
