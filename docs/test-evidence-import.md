# KLONE test evidence: local import and review

The importer accepts **reviewed normalized evidence JSON**, not raw GitHub
workflow artifacts or raw GitHub issue comments. It makes no authenticity
claims. The operator must verify the source independently.

Normalized example:

```json
{
  "source": "github_actions",
  "run_id": "12345",
  "commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "status": "success",
  "observed_at": "2026-11-12T16:00:00Z",
  "environment": "ubuntu-latest-py3.12"
}
```

Run:

```sh
python tools/import_test_evidence.py --database data/test-evidence.sqlite \
  --file reviewed-evidence.json --expected-source github_actions \
  --expected-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

The importer rejects mismatched commit/source, unknown fields, malformed
timestamps, excessive payload sizes, and unsupported statuses. Repeated
identical records are deduplicated. **Do not place API tokens, personal
memory, or private logs in evidence files.**

Raw CI artifacts have a different schema and are not accepted directly.
A future authenticated adapter must validate the GitHub run, job and
commit provenance before producing normalized records. Likewise,
Termux issue comments must not be trusted as independently verified
device identity without additional controls.

View the local dashboard after importing both evidence sources:

```sh
python tools/test_evidence_dashboard.py --database data/test-evidence.sqlite \
  --baseline <baseline-sha> --candidate <candidate-sha> \
  --output klone-test-dashboard.html
```

Neither import nor dashboard automatically approves or deploys code.
