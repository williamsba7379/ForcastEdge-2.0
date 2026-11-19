import os,sys,tempfile,subprocess,unittest
from pathlib import Path
from research.ab_snapshot.p8_generations import GenerationStore,PublicationError,digest

CHILD='''import sys,os
from research.ab_snapshot.p8_generations import GenerationStore
s=GenerationStore(sys.argv[1]); mode=sys.argv[2]
if mode=='activate':
 try:s.activate(2);sys.exit(0)
 except Exception:sys.exit(42)
if mode=='crash':
 import sqlite3
 db=sqlite3.connect(sys.argv[1],isolation_level=None);db.execute('BEGIN IMMEDIATE');db.execute('UPDATE active SET generation=1');os._exit(77)
if mode=='read':
 try:s.read(2,sys.argv[3],lambda p,a,s:None);sys.exit(0)
 except Exception:sys.exit(43)
'''
class P8Processes(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=str(Path(self.tmp.name)/'gen.db');self.s=GenerationStore(self.path)
  self.s.stage(1,b'p1',b'a1',b's1');self.s.activate(1)
  self.s.stage(2,b'p2',b'a2',b's2')
 def child(self,mode):
  return subprocess.run([sys.executable,'-c',CHILD,self.path,mode,digest(b'a2')],cwd=str(Path(__file__).resolve().parents[2]),capture_output=True,timeout=12)
 def test_two_real_processes_compete(self):
  import concurrent.futures
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   codes=list(pool.map(lambda _:self.child('activate').returncode,range(2)))
  self.assertCountEqual(codes,[0,42]);self.assertEqual(self.child('read').returncode,0)
 def test_abrupt_exit_during_uncommitted_activation(self):
  self.assertEqual(self.child('activate').returncode,0)
  self.assertEqual(self.child('crash').returncode,77)
  self.assertEqual(self.child('read').returncode,0)
 def test_staging_not_activated(self):
  with self.assertRaisesRegex(PublicationError,'E804_EXTERNAL_VERSION_MISMATCH'):
   self.s.read(2,digest(b'a2'),lambda p,a,s:None)
