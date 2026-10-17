import unittest
from molio.repeats import summarize


def case(candidate, seed, value=None, status='complete'):
    return {'id':f'{candidate}_{seed}', 'candidate_id':candidate, 'source':{'name':candidate},
            'smiles':candidate, 'seed':seed, 'status':status,
            'prediction': {'affinity':{'affinity_pred_value':value}} if value is not None else None}


def job(cases, seeds=(42,43,44)):
    return {'settings':{'seed':42},'seeds':list(seeds),'cases':cases}


class RepeatTests(unittest.TestCase):
    def test_matching_seeds_not_unpaired_means(self):
        result=summarize(job([case('a',42,1),case('a',43,100),case('a',44,status='failed'),
                              case('b',42,2),case('b',43,status='failed'),case('b',44,-20)]))
        comparison=result['comparisons'][0]
        self.assertEqual(comparison['matched_seeds'],[42])
        self.assertEqual(comparison['mean_delta'],1)
        self.assertEqual(comparison['direction'],'incomplete')
        self.assertEqual(result['candidates'][0]['completed'],2)
        self.assertEqual(result['candidates'][0]['mean'],50.5)

    def test_direction_and_sample_variation(self):
        for values, direction in [([2,3,4],'consistently_higher'),([-2,-3,-4],'consistently_lower'),
                                  ([1,-1,1],'mixed_or_tied'),([0,1,1],'mixed_or_tied')]:
            result=summarize(job([case('a',s,0) for s in (42,43,44)]+[case('b',s,v) for s,v in zip((42,43,44),values)]))
            self.assertEqual(result['comparisons'][0]['direction'],direction)
        stats=summarize(job([case('a',s,v) for s,v in zip((42,43,44),(1,2,3))]))['candidates'][0]
        self.assertEqual((stats['mean'],stats['min'],stats['max'],stats['sample_sd']),(2,1,3,1))

    def test_legacy_single_run_is_not_repeat_evidence(self):
        a=case('a',42,1);b=case('b',42,2)
        for row in (a,b):
            row['id']=row.pop('candidate_id');row.pop('seed')
        result=summarize({'settings':{'seed':42},'cases':[a,b]})
        self.assertEqual(result['comparisons'][0]['direction'],'single_run')
        self.assertIsNone(result['candidates'][0]['sample_sd'])

    def test_duplicate_seed_rejected(self):
        with self.assertRaises(ValueError):summarize(job([case('a',42,1),case('a',42,2)]))

    def test_cancelled_output_excluded(self):
        result=summarize(job([case('a',42,5,status='cancelled')]))
        self.assertEqual(result['candidates'][0]['completed'],0)
        self.assertIsNone(result['candidates'][0]['mean'])

if __name__=='__main__':unittest.main()
