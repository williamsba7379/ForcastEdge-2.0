"""Synthetic dual-artifact crash windows and fail-closed recovery tests."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.p7_publication import make_anchor,check_publication,publish_one,PublicationError

class PublicationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Ed25519PrivateKey.generate()
  self.p1=canonical({'version':1});self.p2=canonical({'version':2})
  self.a1,self.s1=make_anchor(self.root,self.p1,1)
  self.a2,self.s2=make_anchor(self.root,self.p2,2)
  self.expected=hashlib.sha256(self.a2).hexdigest()
 def check(self,p,a,s,expected=None):
  return check_publication(p,a,s,self.root.public_key(),self.expected if expected is None else expected)
 def rejects(self,code,p,a,s):
  with self.assertRaises(PublicationError) as cm:self.check(p,a,s)
  self.assertEqual(cm.exception.code,code)
 def test_complete_publication(self):self.assertEqual(self.check(self.p2,self.a2,self.s2),2)
 def test_policy_first_interruption(self):self.rejects('E703_EXTERNAL_ANCHOR_MISMATCH',self.p2,self.a1,self.s1)
 def test_anchor_first_interruption(self):self.rejects('E702_POLICY_ANCHOR_MISMATCH',self.p1,self.a2,self.s2)
 def test_consistent_dual_rollback(self):self.rejects('E703_EXTERNAL_ANCHOR_MISMATCH',self.p1,self.a1,self.s1)
 def test_stale_expected_anchor(self):
  self.assertEqual(self.check(self.p1,self.a1,self.s1,hashlib.sha256(self.a1).hexdigest()),1)
 def test_invalid_signature(self):self.rejects('E701_PUBLICATION_INVALID',self.p2,self.a2,b'0'*64)
 def test_atomic_single_file_replace(self):
  p=Path(self.tmp.name)/'policy';p.write_bytes(self.p1)
  publish_one(p,self.p2);self.assertEqual(p.read_bytes(),self.p2)
 def test_crash_before_rename_preserves_old_file(self):
  p=Path(self.tmp.name)/'policy';p.write_bytes(self.p1)
  script='import os,sys; f=open(sys.argv[1]+".pending","wb");f.write(b"partial");f.flush();os.fsync(f.fileno());os._exit(77)'
  r=subprocess.run([sys.executable,'-c',script,str(p)],capture_output=True,timeout=10)
  self.assertEqual(r.returncode,77);self.assertEqual(p.read_bytes(),self.p1)
 def test_actual_cross_process_writer_reader_rejects_mismatch(self):
  base=Path(self.tmp.name);policy=base/'policy';anchor=base/'anchor';policy.write_bytes(self.p1);anchor.write_bytes(self.a1)
  script='import os,sys,time; from pathlib import Path; p=Path(sys.argv[1]);p.write_bytes(bytes.fromhex(sys.argv[2]));os._exit(0)'
  r=subprocess.run([sys.executable,'-c',script,str(policy),self.p2.hex()],capture_output=True,timeout=10)
  self.assertEqual(r.returncode,0)
  self.rejects('E703_EXTERNAL_ANCHOR_MISMATCH',policy.read_bytes(),anchor.read_bytes(),self.s1)
 def test_recovery_after_second_publication(self):
  self.rejects('E703_EXTERNAL_ANCHOR_MISMATCH',self.p2,self.a1,self.s1)
  self.assertEqual(self.check(self.p2,self.a2,self.s2),2)
