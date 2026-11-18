# Session changelog

## 2026-11-18 — Final-project review

- Recovered the original five scored retrieval experiments, load trial and dashboard captures from a read-only Ubuntu disk. The [review evidence](../reports/review/README.md) distinguishes historical observations from new checks.
- Pinned the verified `setup-uv` action commit and included DVC in the locked development environment. The PR evidence check is offline; it is not a new RAGAS score. Live evaluation still requires protected credentials.
- Separated hosted reviewer inference from the GPU benchmark. The former free embedding route returned HTTP 404 during verification; the reviewer replacement returned 2,048 numeric embedding values. No production index was reused.
- Reproduced both DVC stages from the committed PDF: 1,149 articles and matching output hashes. The local MLflow alias resolved to the same recipe version on repeat, and an incomplete comparison was rejected without moving it.
- On CachyOS, Python 3.12 with the copied WSL dependency set passed 292 tests at 88.22% source coverage. The reviewer Docker archive also passed all file and bundle checksum checks.
