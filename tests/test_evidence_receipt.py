import copy
import secrets
import unittest
from klone.evidence_receipt import EvidenceError, digest, make_subject, sign, verify


def record(fields):
    result = copy.deepcopy(fields)
    result['report_sha256'] = digest(result)
    return result


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.secret = secrets.token_bytes(32)
        self.dossier = record({
            'cards': [{'candidate_id': 'a1', 'source': 'A'},
                      {'candidate_id': 'a2', 'source': 'A'},
                      {'candidate_id': 'b1', 'source': 'B'}],
            'sources': {
                'A': {'source_event_id': 11, 'arxiv_id': '2611.13801v1'},
                'B': {'source_event_id': 12, 'arxiv_id': '2611.15598v1'}},
        })
        self.debate = record({'e11_report_sha256': self.dossier['report_sha256']})
        self.args = dict(proposal_id='p1', target_version='v1', draft_text='Unverified draft',
                         ids=['a1','b1'], dossier=self.dossier, debate=self.debate)
        self.subject = make_subject(**self.args)
        self.receipt = sign(self.subject, secret=self.secret, issued_at=1000)

    def test_roundtrip(self):
        self.assertTrue(verify(self.receipt, self.subject, secret=self.secret, now=1001))

    def test_two_works_not_verified(self):
        self.assertEqual(self.subject['distinct_arxiv_works'], 2)
        self.assertFalse(self.subject['scientific_claim_verified'])

    def test_multiple_cards_same_work(self):
        s = make_subject(**{**self.args, 'ids': ['a1','a2']})
        self.assertEqual(s['distinct_arxiv_works'], 1)

    def test_wrong_signing_key(self):
        with self.assertRaises(EvidenceError):
            verify(self.receipt, self.subject, secret=secrets.token_bytes(32), now=1001)

    def test_changed_draft(self):
        other = make_subject(**{**self.args, 'draft_text': 'changed'})
        with self.assertRaises(EvidenceError):
            verify(self.receipt, other, secret=self.secret, now=1001)

    def test_changed_proposal(self):
        other = make_subject(**{**self.args, 'proposal_id': 'p2'})
        with self.assertRaises(EvidenceError):
            verify(self.receipt, other, secret=self.secret, now=1001)

    def test_changed_cards(self):
        other = make_subject(**{**self.args, 'ids': ['a1']})
        with self.assertRaises(EvidenceError):
            verify(self.receipt, other, secret=self.secret, now=1001)

    def test_changed_version(self):
        other = make_subject(**{**self.args, 'target_version': 'v2'})
        with self.assertRaises(EvidenceError):
            verify(self.receipt, other, secret=self.secret, now=1001)

    def test_expired(self):
        with self.assertRaises(EvidenceError):
            verify(self.receipt, self.subject, secret=self.secret, now=1300)

    def test_future(self):
        with self.assertRaises(EvidenceError):
            verify(self.receipt, self.subject, secret=self.secret, now=999)

    def test_forged_field(self):
        forged = copy.deepcopy(self.receipt)
        forged['body']['subject']['scientific_claim_verified'] = True
        with self.assertRaises(EvidenceError):
            verify(forged, self.subject, secret=self.secret, now=1001)

    def test_reject_extra_envelope(self):
        forged = {**self.receipt, 'release_authorized': True}
        with self.assertRaises(EvidenceError):
            verify(forged, self.subject, secret=self.secret, now=1001)

    def test_unknown_card(self):
        with self.assertRaises(EvidenceError):
            make_subject(**{**self.args, 'ids': ['not-real']})

    def test_duplicate_card(self):
        with self.assertRaises(EvidenceError):
            make_subject(**{**self.args, 'ids': ['a1','a1']})

    def test_report_changed(self):
        corrupted = copy.deepcopy(self.dossier)
        corrupted['sources']['A']['arxiv_id'] = '2611.12345v1'
        with self.assertRaises(EvidenceError):
            make_subject(**{**self.args, 'dossier': corrupted})

    def test_report_link_changed(self):
        corrupted = record({**self.dossier, 'cards': self.dossier['cards'][:-1], 'report_sha256': 'fake'})
        with self.assertRaises(EvidenceError):
            make_subject(**{**self.args, 'dossier': corrupted})

    def test_empty_ids(self):
        with self.assertRaises(EvidenceError):
            make_subject(**{**self.args, 'ids': []})

    def test_no_publish(self):
        subj = dict(self.subject, action='publish_verified')
        with self.assertRaises(EvidenceError):
            sign(subj, secret=self.secret, issued_at=1000)

    def test_draft_missing(self):
        with self.assertRaises(EvidenceError):
            make_subject(**{**self.args, 'draft_text': '  '})

    def test_bad_ttl(self):
        with self.assertRaises(EvidenceError):
            sign(self.subject, secret=self.secret, issued_at=1000, ttl=400)


if __name__ == '__main__':
    unittest.main()
