| chunking | mode | chunks | doc@1 | sec@1 | sec@5 | mrr@10 | tokens@1 |
|---|---|---|---|---|---|---|---|
| heading-aware (180) | dense | 144 | 0.966 | 0.466 | 0.886 | 0.615 | 25.4 |
| heading-aware (180) | sparse | 144 | 0.955 | 0.432 | 0.898 | 0.604 | 25.4 |
| heading-aware (180) | hybrid | 144 | 0.955 | 0.466 | 0.92 | 0.622 | 25.1 |
| fixed window (60) | dense | 112 | 0.841 | 0.545 | 0.727 | 0.632 | 57.5 |
| fixed window (60) | sparse | 112 | 0.875 | 0.534 | 0.864 | 0.659 | 57.6 |
| fixed window (60) | hybrid | 112 | 0.886 | 0.568 | 0.864 | 0.681 | 57.1 |
| fixed window (180) | dense | 39 | 0.92 | 0.92 | 0.977 | 0.939 | 162.8 |
| fixed window (180) | sparse | 39 | 0.955 | 0.955 | 0.966 | 0.958 | 158.9 |
| fixed window (180) | hybrid | 39 | 0.943 | 0.943 | 0.977 | 0.96 | 159.0 |

| incremental ingest | value |
|---|---|
| first run embeddings | 144 |
| repeat run embeddings | 0 |
| docs edited | 4 |
| docs deleted | 2 |
| docs added | 2 |
| incremental embeddings | 14 |
| full reindex embeddings | 144 |
| embedding work saved | 0.903 |
| chunks removed | 14 |
