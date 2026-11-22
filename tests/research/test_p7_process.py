"""P7 actual subprocess regressions, synthetic SQLite only."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing

SCRIPT = '''import sqlite3,sys,os,time
p,action=sys.argv[1:]
if action=='crash':
 c=sqlite3.connect(p,isolation_level=None);c.execute('BEGIN IMMEDIATE');c.execute('UPDATE state SET version=3');os._exit(77)
if action=='update':
 c=sqlite3.connect(p,timeout=5,isolation_level=None)
 try:
  c.execute('BEGIN IMMEDIATE');v=c.execute('SELECT version FROM state').fetchone()[0]
  if v>=2: c.rollback();sys.exit(42)
  c.execute('UPDATE state SET version=2');c.commit();sys.exit(0)
 finally:c.close()
if action=='read':
 c=sqlite3.connect(p);v=c.execute('SELECT version FROM state').fetchone()[0];c.close();sys.exit(0 if v==2 else 43)
'''

class P7ProcessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=os.path.join(self.tmp.name,'state.db')
  with closing(sqlite3.connect(self.path)) as db,db:
   db.execute('CREATE TABLE state(version INTEGER NOT NULL)');db.execute('INSERT INTO state VALUES (1)')
 def run_child(self,action):
  return subprocess.run([sys.executable,'-c',SCRIPT,self.path,action],capture_output=True,timeout=15)
 def version(self):
  with closing(sqlite3.connect(self.path)) as db:return db.execute('SELECT version FROM state').fetchone()[0]
 def test_two_independent_writers_only_one_commits(self):
  import concurrent.futures
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   codes=list(pool.map(lambda _:self.run_child('update').returncode,range(2)))
  self.assertCountEqual(codes,[0,42]);self.assertEqual(self.version(),2)
 def test_abrupt_process_exit_rolls_back_uncommitted_update(self):
  self.assertEqual(self.run_child('update').returncode,0)
  self.assertEqual(self.run_child('crash').returncode,77)
  self.assertEqual(self.version(),2)
 def test_separate_process_reads_committed_version(self):
  self.assertEqual(self.run_child('update').returncode,0)
  self.assertEqual(self.run_child('read').returncode,0)
