# Review evidence

- [Five completed MLflow runs](mlflow-comparison.csv): the final `2026-10-16-super-candidate-v2` comparison uses the same 62 bilingual questions and judge profile for each retrieval configuration. The local `rag-ishms-retrieval-config@candidate` alias resolved to version 1 of the [selected recipe](selected-retrieval-config.json); its [provenance](mlflow-provenance.json) records the artifact digest and source run. This is neither a trained model nor a production deployment.
- [Locust HTML](load/load.html), [statistics](load/load_stats.csv), [failures](load/load_failures.csv) and [final counts after drain](load/load-final.json): the isolated PGVector API trial used 50 identities. The periodic snapshot recorded 57 answer requests and 49 failures; after drain there were **58 requests and 50 failures**, p95 **180 seconds**. This did not meet the capacity target. It was not a measurement of nginx or the hosted reviewer profile.
- [Grafana capture](grafana.png): RAG-ISHMS / Quality by language, last six hours on October 16, 2026. The published `article-rerank` report at 04:14 UTC had SHA-256 `78ea9922b40067c8d2ffd4814ffb8263fcae7ad5bcc6247b9e42916aa09123a6`. Earlier points used different judge profiles; they are not a model-improvement trend. The isolated load API was not scraped here.

The load files and image were checked against the original evidence archive manifest before export. See the [measured report](../../docs/final-project-report.md) for model identifiers, limitations and judge errors.

To recreate the alias from the original evidence without regenerating answers or
relogging runs, run from the repository root after installing the `eval` group:

```sh
evidence=eval/reports/final-project
state="$HOME/.local/share/rag-ishms/review-registry"
mkdir -p -m 700 "$state"
test -f "$state/mlflow.db" || cp "$evidence/mlflow.db" "$state/mlflow.db"
uv run --locked --group eval python scripts/run_experiments.py \
  --resume --register-selected \
  --dataset eval/civil_code_full.json --corpus "$evidence/corpus/articles.json" \
  --reports "$evidence/configurations-super-candidate-v2" \
  --tracking-uri "sqlite:///$state/mlflow.db" \
  --run-inventory "$evidence/mlflow-release.json" \
  --registry-artifacts "$state/artifacts" --review-export reports/review
```

The private database and raw reports are not in Git; the CSV and JSON exports
are portable. The SQLite alias requires the original run database and the local
artifact directory. The command must not be pointed at a serving registry.
