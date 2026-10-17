import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from molecular_lab.experiments import Experiments, catalog, target_sequence, read_result
from molecular_lab.proposals import ProposalStore, available
from molecular_lab.server import load_dataset


@unittest.skipUnless(available(), 'RDKit required')
class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = ProposalStore(self.root/'proposals.sqlite3')
        self.data = load_dataset()
        self.rows = catalog(self.data, [])
        self.jobs = Experiments(self.root/'experiments', self.store)
        self.addCleanup(self.jobs.close)

    def payload(self, index=5):
        row = self.rows[index]
        return {'candidates':[{'id':row['id'], 'smiles':row['stereo_options'][0]}], 'msa_mode':'empty'}

    def test_sequence_and_stereo_preserve_source(self):
        sequence, source = target_sequence()
        self.assertEqual(len(sequence),125)
        self.assertEqual(source['expression_tags_removed'],[42,43])
        self.assertTrue(sequence.startswith('NPPPP'))
        alcohol = next(c for c in self.rows if c['id']=='CHEMBL1828982')
        self.assertEqual(len(alcohol['stereo_options']),2)
        self.assertNotIn('@',alcohol['smiles'])
        self.assertTrue(all('@' in s for s in alcohol['stereo_options']))
        self.assertEqual(alcohol['observation']['value'],9700)

    def test_preflight_and_strict_inputs(self):
        with self.assertRaises(RuntimeError): self.jobs.submit(self.payload(),self.data)
        for payload in [{},dict(self.payload(), command=['anything']),dict(self.payload(),msa_mode='server'),
                        dict(self.payload(),candidates=[]),dict(self.payload(),candidates=self.payload()['candidates']*4),
                        dict(self.payload(),candidates=[{'id':self.rows[0]['id'],'smiles':'CC'}]),
                        dict(self.payload(),candidates=self.payload()['candidates']*2)]:
            with self.subTest(payload=payload),self.assertRaises(ValueError): self.jobs.submit(payload,self.data)
        for identifier in ['../x','unknown',None]:
            with self.assertRaises(ValueError): self.jobs.get(identifier)

    def test_queue_restart_and_cancellation(self):
        self.jobs.health={'ready':True,'version':'2.2.1'}
        with patch.object(self.jobs.pool,'submit'):
            job=self.jobs.submit(self.payload(),self.data)
        self.assertIsNone(job['cases'][0]['prediction'])
        with self.assertRaises(RuntimeError):self.jobs.submit(self.payload(6),self.data)
        self.assertTrue(self.jobs.cancel(job['id'])['cancel_requested'])
        with self.assertRaisesRegex(RuntimeError, 'already owns'):
            Experiments(self.jobs.directory,self.store)
        self.jobs.close()
        other=Experiments(self.jobs.directory,self.store)
        self.addCleanup(other.close)
        self.assertEqual(other.get(job['id'])['status'],'interrupted')

    def test_failure_is_persistent_not_a_score(self):
        self.jobs.health={'ready':True,'version':'2.2.1'}
        self.jobs.executable='/bin/false'
        job=self.jobs.submit(self.payload(),self.data)
        for _ in range(100):
            result=self.jobs.get(job['id'])
            if result['status']=='failed':break
            time.sleep(.02)
        self.assertEqual(result['status'],'failed')
        self.assertIsNone(result['cases'][0]['prediction'])
        self.assertTrue(result['cases'][0]['input_sha256'])

    def test_three_seeds_are_bounded_and_matched(self):
        self.jobs.health={'ready':True,'version':'2.2.1'}
        for value in [0,2,4,True,'3',None]:
            with self.assertRaises(ValueError):
                self.jobs.submit(dict(self.payload(),repeats=value),self.data)
        payload=self.payload()
        payload['candidates'] += self.payload(6)['candidates']
        payload['repeats']=3
        with patch.object(self.jobs.pool,'submit'):
            result=self.jobs.submit(payload,self.data)
        self.assertEqual(len(result['cases']),6)
        self.assertEqual([c['seed'] for c in result['cases']],[42,42,43,43,44,44])
        self.assertEqual(len({c['id'] for c in result['cases']}),6)
        self.assertEqual(len(result['comparison']['candidates']),2)
        self.assertTrue(all(c['expected']==3 for c in result['comparison']['candidates']))

    def test_cancellation_stops_a_real_subprocess(self):
        executable=self.root/'slow-worker'
        executable.write_text('#!/bin/sh\nsleep 60\n')
        executable.chmod(0o700)
        self.jobs.health={'ready':True,'version':'2.2.1'}
        self.jobs.executable=str(executable)
        job=self.jobs.submit(self.payload(),self.data)
        for _ in range(100):
            if job['id'] in self.jobs.processes: break
            time.sleep(.02)
        self.assertIn(job['id'],self.jobs.processes)
        process=self.jobs.processes[job['id']]
        self.jobs.cancel(job['id'])
        for _ in range(100):
            result=self.jobs.get(job['id'])
            if result['status']=='cancelled': break
            time.sleep(.02)
        self.assertEqual(result['status'],'cancelled')
        self.assertIsNotNone(process.poll())
        self.assertIsNone(result['cases'][0]['prediction'])

    def test_output_validation_rejects_missing_invalid_and_wrong_identity(self):
        out=self.root/'outputs';out.mkdir()
        with self.assertRaises(ValueError):read_result(out,'x',1)
        (out/'affinity_x.json').write_text('{"affinity_pred_value": NaN, "affinity_probability_binary": 0.5}')
        (out/'confidence_x_model_0.json').write_text('{"confidence_score": 0.8}')
        (out/'x_model_0.pdb').write_text('')
        with self.assertRaisesRegex(ValueError,'Nonfinite'):read_result(out,'x',1)
        (out/'affinity_x.json').write_text('{"affinity_pred_value": 1.2, "affinity_probability_binary": 0.5}')
        with self.assertRaisesRegex(ValueError,'chains'):read_result(out,'x',1)

if __name__=='__main__':unittest.main()
