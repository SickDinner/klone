import tempfile
from pathlib import Path
import unittest

from klone.research_signed_grants import issue_research_grant
from klone.research_grant_nonce_ledger import claim_research_grant_nonce


class ResearchGrantNonceTests(unittest.TestCase):
    def test_claim_once_across_connections(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nonce.sqlite"
            key = b"k" * 32
            grant = issue_research_grant(
                principal="researcher", resource_id="dossier",
                report_version=1, policy_version=1, expires_at=200,
                nonce="unique-nonce-123456", key=key)
            args = dict(database_path=db, grant=grant, principal="researcher",
                        resource_id="dossier", report_version=1,
                        policy_version=1, now=100, key=key)
            self.assertTrue(claim_research_grant_nonce(**args))
            self.assertFalse(claim_research_grant_nonce(**args))

    def test_expired_grant_does_not_create_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nonce.sqlite"
            key = b"k" * 32
            grant = issue_research_grant(
                principal="researcher", resource_id="dossier",
                report_version=1, policy_version=1, expires_at=100,
                nonce="unique-nonce-123456", key=key)
            self.assertFalse(claim_research_grant_nonce(
                database_path=db, grant=grant, principal="researcher",
                resource_id="dossier", report_version=1,
                policy_version=1, now=100, key=key))
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
