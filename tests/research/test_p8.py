import multiprocessing as mp
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from research.ab_snapshot.p8_generations import GenerationStore, PublicationError, digest

def writer(args):
    path,gen=args
    try:
        GenerationStore(path).activate(gen)
        return 'ok'
    except PublicationError as exc:
        return str(exc)

def reader(args):
    path,version,anchor=args
    try:
        return GenerationStore(path).read(version,digest(anchor),lambda p,a,s: None)
    except PublicationError as exc:
        return str(exc)

class P8(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=os.path.join(self.tmp.name,'state.db')
        self.store=GenerationStore(self.path)
        self.store.stage(1,b'p1',b'a1',b's1');self.store.activate(1)
    def test_active_generation(self):self.assertEqual(reader((self.path,1,b'a1')),1)
    def test_interrupted_staging(self):
        self.store.stage(2,b'p2',b'a2',b's2')
        self.assertEqual(reader((self.path,1,b'a1')),1)
    def test_activation_switch(self):
        self.store.stage(2,b'p2',b'a2',b's2');self.store.activate(2)
        self.assertEqual(reader((self.path,2,b'a2')),2)
    def test_stale_external_anchor(self):
        self.store.stage(2,b'p2',b'a2',b's2');self.store.activate(2)
        self.assertEqual(reader((self.path,1,b'a1')),'E804_EXTERNAL_VERSION_MISMATCH')
    def test_consistent_rollback_requires_external_anchor(self):
        self.store.stage(2,b'p2',b'a2',b's2');self.store.activate(2)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE active SET generation=1')
            db.commit()
        self.assertEqual(reader((self.path,2,b'a2')),'E804_EXTERNAL_VERSION_MISMATCH')
    def test_corrupted_anchor(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE generations SET anchor=? WHERE id=1',(b'bad',))
            db.commit()
        self.assertEqual(reader((self.path,1,b'a1')),'E805_EXTERNAL_ANCHOR_MISMATCH')
    def test_missing_generation(self):
        with self.assertRaisesRegex(PublicationError,'E803_MISSING_GENERATION'):self.store.activate(3)
    def test_monotonic_activation(self):
        with self.assertRaisesRegex(PublicationError,'E802_ROLLBACK'):self.store.activate(1)
    def test_cross_process_writers(self):
        self.store.stage(2,b'p2',b'a2',b's2')
        with ProcessPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(writer,[(self.path,2)]*2))
        self.assertCountEqual(results,['ok','E802_ROLLBACK'])
    def test_cross_process_reader(self):
        self.store.stage(2,b'p2',b'a2',b's2');self.store.activate(2)
        with ProcessPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reader,[(self.path,2,b'a2'),(self.path,1,b'a1')]))
        self.assertEqual(results,[2,'E804_EXTERNAL_VERSION_MISMATCH'])

if __name__=='__main__':unittest.main()
