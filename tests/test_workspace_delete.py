"""Deletion boundaries: confirmation, active runs, isolation and path safety."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from molio.targets import Workspaces
from molio.server import Handler


class WorkspaceDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manager = Workspaces(self.root)
        self.addCleanup(self.manager.close)
        self.key = 'lab-123456789abc'
        self.folder = self.manager.directory/self.key
        (self.folder/'data').mkdir(parents=True)
        (self.folder/'data/dataset.json').write_text(json.dumps({'workspace_id':self.key,'target':{'name':'Test protein'},'compounds':[]}))
        self.other = self.manager.directory/'lab-abcdef123456'
        self.other.mkdir()
        (self.other/'keep.txt').write_text('keep')
        self.cache = self.root/'boltz-cache'
        self.cache.mkdir()
        (self.cache/'weights').write_text('keep')
        self.jobs = SimpleNamespace(directory=self.root/'experiments',lock=threading.RLock())
        self.jobdir = self.jobs.directory/'test-job'
        self.jobdir.mkdir(parents=True)
        (self.jobdir/'result').write_text('result')
        self.job = {'id':'test-job','workspace_id':self.key,'status':'complete'}
        self.jobs.list = lambda: [self.job]

    def test_delete_removes_owned_data_only(self):
        result = self.manager.delete(self.key,self.jobs)
        self.assertEqual(result['experiments_deleted'],1)
        self.assertFalse(self.folder.exists())
        self.assertFalse(self.jobdir.exists())
        self.assertTrue((self.other/'keep.txt').is_file())
        self.assertTrue((self.cache/'weights').is_file())
        with self.assertRaises(ValueError): self.manager.delete(self.key,self.jobs)

    def test_reject_active_and_invalid_paths_without_changes(self):
        for status in ('queued','preparing','running','validating'):
            self.job['status']=status
            with self.assertRaises(ValueError): self.manager.delete(self.key,self.jobs)
            self.assertTrue(self.folder.exists())
            self.assertTrue(self.jobdir.exists())
        for key in ('brd4','../outside','lab-000000000000'):
            with self.assertRaises(ValueError): self.manager.delete(key,self.jobs)
        link=self.manager.directory/'lab-111111111111'
        link.symlink_to(self.folder,target_is_directory=True)
        with self.assertRaises(ValueError): self.manager.delete(link.name,self.jobs)
        self.assertTrue(self.folder.exists())

    def test_api_requires_confirmation_and_rejects_cross_origin(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.workspaces=self.manager
        server.experiments=self.jobs
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            def request(payload, origin=None):
                headers={'Content-Type':'application/json'}
                if origin: headers['Origin']=origin
                req=Request(f'http://127.0.0.1:{server.server_port}/api/workspaces/delete',data=json.dumps(payload).encode(),headers=headers)
                return urlopen(req)
            for payload,origin,status in [({'id':self.key},None,400),({'id':self.key,'confirm':False},None,400),({'id':self.key,'confirm':True},'http://elsewhere',403)]:
                with self.assertRaises(HTTPError) as error: request(payload,origin)
                self.assertEqual(error.exception.code,status)
                self.assertTrue(self.folder.exists())
            with request({'id':self.key,'confirm':True}) as response:
                self.assertEqual(json.load(response)['deleted'],self.key)
        finally:
            server.shutdown();server.server_close();thread.join()
