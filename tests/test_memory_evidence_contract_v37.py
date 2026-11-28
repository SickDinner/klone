"""Offline synthetic evaluation contract; not a production memory integration."""
import unittest
from collections import Counter


# Each case represents a synthetic answer review, not actual user data.
# Labels are supplied by the reviewer, never inferred by a model.
CASES = (
    ('current', 'supported'),
    ('superseded', 'stale'),
    ('deleted', 'stale'),
    ('missing', 'abstain'),
    ('conflicting', 'abstain'),
    ('wrong_room', 'blocked'),
)
LABELS = frozenset({'supported', 'stale', 'abstain', 'blocked'})


def evaluate(expected, observed):
    """Compare complete, explicitly labeled synthetic review records."""
    def index(rows):
        result = {}
        for key, label in rows:
            if not isinstance(key, str) or not key or key in result:
                raise ValueError('invalid or duplicate case id')
            if label not in LABELS:
                raise ValueError('invalid label')
            result[key] = label
        return result

    truth, actual = index(expected), index(observed)
    if not truth or truth.keys() != actual.keys():
        raise ValueError('nonempty matching case coverage required')
    mismatches = sorted(k for k in truth if truth[k] != actual[k])
    expected_counts = Counter(truth.values())
    correct_counts = Counter(truth[k] for k in truth if truth[k] == actual[k])
    return {
        'cases': len(truth),
        'correct': len(truth) - len(mismatches),
        'mismatches': mismatches,
        'by_label': {label: {'correct': correct_counts[label],
                             'total': expected_counts[label]}
                     for label in sorted(LABELS)},
        'passed': not mismatches,
    }


class MemoryEvidenceContractV37(unittest.TestCase):
    def test_complete_reference(self):
        result = evaluate(CASES, CASES)
        self.assertEqual(result['correct'], 6)
        self.assertTrue(result['passed'])

    def test_stale_answer_not_counted_as_supported(self):
        actual = [(k, 'supported' if k == 'superseded' else v) for k, v in CASES]
        result = evaluate(CASES, actual)
        self.assertEqual(result['mismatches'], ['superseded'])
        self.assertEqual(result['by_label']['stale'], {'correct': 1, 'total': 2})
        self.assertFalse(result['passed'])

    def test_abstention_not_equivalent_to_correct_answer(self):
        result = evaluate(CASES, [(k, 'abstain') for k, _ in CASES])
        self.assertEqual(result['correct'], 2)

    def test_room_violation_detected(self):
        actual = [(k, 'supported' if k == 'wrong_room' else v) for k, v in CASES]
        self.assertEqual(evaluate(CASES, actual)['by_label']['blocked']['correct'], 0)

    def test_order_independence(self):
        self.assertEqual(evaluate(CASES, CASES), evaluate(reversed(CASES), reversed(CASES)))

    def test_missing_case_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(CASES, CASES[:-1])

    def test_extra_case_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(CASES, CASES + (('extra', 'abstain'),))

    def test_duplicate_case_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(CASES, CASES + CASES[:1])

    def test_unknown_label_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(CASES, CASES[:-1] + (('wrong_room', 'unknown'),))

    def test_empty_evaluation_rejected(self):
        with self.assertRaises(ValueError):
            evaluate((), ())


if __name__ == '__main__':
    unittest.main()
