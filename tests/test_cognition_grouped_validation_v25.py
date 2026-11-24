import math
import unittest
from dataclasses import FrozenInstanceError
from klone.cognition_grouped_validation_v25 import GroupedPrediction, evaluate_grouped_predictions


def row(item,group,confidence,correct):
    return GroupedPrediction(item,group,confidence,correct)


def score(rows,groups=frozenset(),**kwargs):
    return evaluate_grouped_predictions(rows,training_source_groups=groups,**kwargs)


class GroupedCognitionV25Tests(unittest.TestCase):
    def test_one_source_fanned_to_72_agents_is_still_one_group(self):
        data=[row(f'agent{i}','same-evidence',1.0,True) for i in range(1,73)]
        result=score(data)
        self.assertEqual(result['prediction_count'],72)
        self.assertEqual(result['declared_source_group_count'],1)
        self.assertEqual(result['assessment'],'insufficient_declared_groups')
        self.assertFalse(result['independent_sources_verified'])
        self.assertFalse(result['deployment_approval'])

    def test_mass_duplicated_bad_source_vs_distinct_good_source(self):
        data=[row(f'a{i}','source-A',1,False) for i in range(99)]
        data.append(row('b0','source-B',1,True))
        result=score(data,minimum_declared_groups=2)
        self.assertAlmostEqual(result['naive_brier'],0.99)
        self.assertAlmostEqual(result['source_group_balanced_brier'],0.5)
        self.assertEqual(result['largest_declared_group_fraction'],0.99)
        self.assertFalse(result['independent_sources_verified'])

    def test_perfect_predictions(self):
        data=[row('a','a',1,True),row('b','b',0,False)]
        result=score(data,minimum_declared_groups=2)
        self.assertEqual(result['naive_brier'],0)
        self.assertEqual(result['source_group_balanced_ece'],0)

    def test_confident_wrong(self):
        result=score([row('one','first',1,False)])
        self.assertEqual(result['naive_brier'],1)
        self.assertEqual(result['source_group_balanced_ece'],1)

    def test_balanced_ece_midpoint(self):
        result=score([row('a','a',0.5,False),row('b','b',0.5,True)],minimum_declared_groups=2)
        self.assertEqual(result['source_group_balanced_ece'],0)

    def test_training_group_overlap_denied(self):
        with self.assertRaisesRegex(ValueError,'lineage_overlap'):
            score([row('p','source-x',.5,True)],frozenset({'source-x'}))

    def test_synthetic_distinct_labels_do_not_prove_independence(self):
        result=score([row(f'p{i}',f'label-{i}',.8,True) for i in range(6)])
        self.assertFalse(result['independent_sources_verified'])
        self.assertEqual(result['assessment'],'manual_review_required')

    def test_multiple_sources_do_not_approve_deployment(self):
        result=score([row(f'p{i}',f's{i}',.9,True) for i in range(50)])
        self.assertFalse(result['autonomous_decisions_allowed'])
        self.assertFalse(result['deployment_approval'])

    def test_wrong_truth_type_rejected(self):
        for value in (1,0,None,'yes'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                row('a','group',.9,value)

    def test_nonfinite_confidence_rejected(self):
        for x in (float('nan'),float('inf'),-float('inf')):
            with self.subTest(x=x),self.assertRaises(ValueError):
                row('a','group',x,True)

    def test_wrong_confidence_types_rejected(self):
        for x in (True,'0.9',None,-1,1.1):
            with self.subTest(x=x),self.assertRaises(ValueError):
                row('a','group',x,True)

    def test_duplicate_item_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate_prediction_item'):
            score([row('a','source1',0.5,True),row('a','source2',0.5,True)])

    def test_invalid_group_names_rejected(self):
        for group in ('','../escape','foo bar',None,'a'*200):
            with self.subTest(group=group),self.assertRaises(ValueError):
                row('x',group,.5,True)

    def test_empty_invalid_collection(self):
        for rows in ([],None,'hello',b'hello',{}):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                score(rows)

    def test_training_group_set_must_be_explicit_frozenset(self):
        with self.assertRaises(ValueError):
            score([row('a','group',0.5,True)],{'train'})

    def test_invalid_bin_count(self):
        for value in (0,1,101,True,5.2):
            with self.subTest(bins=value),self.assertRaises(ValueError):
                score([row('a','group',.5,True)],calibration_bins=value)

    def test_invalid_min_groups(self):
        for value in (0,1025,True,'2'):
            with self.subTest(n=value),self.assertRaises(ValueError):
                score([row('a','group',.5,True)],minimum_declared_groups=value)

    def test_result_independent_of_input_row_order(self):
        rows=[row('a','two',.3,False),row('b','one',.8,True),row('c','two',.4,True)]
        self.assertEqual(score(rows),score(list(reversed(rows))))

    def test_frozen_predictions(self):
        p=row('a','source',.5,True)
        with self.assertRaises(FrozenInstanceError):
            p.correct=False

    def test_no_training_side_effects(self):
        rows=[row('a','source',.5,True)]
        before=list(rows)
        score(rows)
        self.assertEqual(rows,before)

    def test_brier_has_correct_ordinary_mean_when_one_per_group(self):
        rows=[row('a','A',0.2,False),row('b','B',0.8,True)]
        out=score(rows)
        self.assertAlmostEqual(out['naive_brier'],0.04)
        self.assertAlmostEqual(out['source_group_balanced_brier'],0.04)

    def test_bad_prediction_object_denied(self):
        with self.assertRaises(ValueError):score([{'item_id':'a'}])

if __name__=='__main__':unittest.main()
