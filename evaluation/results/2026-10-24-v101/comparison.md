# Frozen synthetic retrieval baselines

Answers are not evaluated. Latency includes query embedding for vector/hybrid.

| Mode | Recall@1 | Recall@3 | Recall@5 | Mean ms | P95 ms | Positive graph hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| keyword | 0.0000 | 0.0000 | 0.0000 | 7.7 | 22.3 | 0 |
| vector | 0.5009 | 0.8722 | 0.9806 | 218.8 | 238.9 | 0 |
| hybrid | 0.3681 | 0.5644 | 0.6602 | 232.8 | 250.4 | 182 |
