import unittest

from cyp_pipeline.design import rank_candidates, score_pose_summary, tanimoto


def summary(deltas, b1=None, b2=None):
    b1 = b1 or [-1.0] * len(deltas)
    b2 = b2 or [-1.0] * len(deltas)
    return {
        "cycles": [
            {
                "B1_exchange_eV": left,
                "B2_exchange_eV": right,
                "B2_minus_B1_eV": delta,
            }
            for delta, left, right in zip(deltas, b1, b2)
        ]
    }


class DesignScoringTests(unittest.TestCase):
    def test_b1_requires_positive_full_pose_range(self):
        score = score_pose_summary(summary([0.08, 0.12, 0.10]), "CYP11B1", 0.05)
        self.assertTrue(score["lead_eligible"])
        self.assertAlmostEqual(score["robust_selectivity_eV"], 0.08)
        self.assertAlmostEqual(score["selectivity_margin_over_floor_eV"], 0.03)

    def test_sign_crossing_is_not_a_b1_lead(self):
        score = score_pose_summary(summary([-0.01, 0.20]), "CYP11B1", 0.05)
        self.assertFalse(score["lead_eligible"])
        self.assertEqual(score["delta_B2_minus_B1_range_eV"], [-0.01, 0.2])

    def test_b2_uses_inverse_delta_direction(self):
        score = score_pose_summary(summary([-0.20, -0.09, -0.12]), "CYP11B2", 0.05)
        self.assertTrue(score["lead_eligible"])
        self.assertAlmostEqual(score["robust_selectivity_eV"], 0.09)

    def test_target_exchange_gate_is_separate(self):
        score = score_pose_summary(
            summary([0.20, 0.21, 0.22], b1=[-0.1, 0.02, -0.2]), "CYP11B1", 0.05
        )
        self.assertTrue(score["passes_selectivity_gate"])
        self.assertFalse(score["passes_target_exchange_gate"])
        self.assertFalse(score["lead_eligible"])

    def test_single_pose_is_baseline_only(self):
        score = score_pose_summary(summary([0.30]), "CYP11B1", 0.05)
        self.assertTrue(score["passes_selectivity_gate"])
        self.assertFalse(score["passes_pose_count_gate"])
        self.assertFalse(score["lead_eligible"])

    def test_tanimoto(self):
        self.assertEqual(tanimoto([1, 2], [1, 2]), 1.0)
        self.assertEqual(tanimoto([1], [2]), 0.0)
        self.assertAlmostEqual(tanimoto([1, 2], [2, 3]), 1 / 3)

    def test_ranking_excludes_observed_candidate(self):
        campaign = {
            "model": {"minimum_observations_for_surrogate": 4},
            "candidates": [
                {"id": "known", "name": "known", "canonical_smiles": "C",
                 "fingerprint_bits": [1], "hypothesis_priority_eV": 0, "rationale": "known"},
                {"id": "new", "name": "new", "canonical_smiles": "CC",
                 "fingerprint_bits": [1, 2], "hypothesis_priority_eV": 0.1,
                 "rationale": "new", "flags": []},
            ],
            "observations": [{"candidate_id": "known", "robust_selectivity_eV": -0.1,
                              "eligible_for_model": True, "model_weight": 1.0}],
        }
        ranked = rank_candidates(campaign)
        self.assertEqual([row["candidate_id"] for row in ranked], ["new"])


if __name__ == "__main__":
    unittest.main()
