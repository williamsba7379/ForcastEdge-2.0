"""Synthetic-only signed cross-process generation read; no NFL data or network."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from research.ab_snapshot.p8_generations import GenerationStore, digest
from research.ab_snapshot.p7_publication import make_anchor
from research.ab_snapshot.validator import canonical

CHILD = '''import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from research.ab_snapshot.p8_generations import GenerationStore
from research.ab_snapshot.p7_publication import check_publication
store=GenerationStore(sys.argv[1])
key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(sys.argv[4]))
try:
 store.read(1,sys.argv[2],lambda p,a,s:check_publication(p,a,s,key,sys.argv[2]))
except Exception:
 sys.exit(43)
sys.exit(0)
'''

class P8SignedProcess(unittest.TestCase):
 def test_real_signed_reader_in_independent_process(self):
  with tempfile.TemporaryDirectory() as d:
   path=os.path.join(d,'gen.db')
   private=Ed25519PrivateKey.generate()
   policy=canonical({'version':1})
   anchor,sig=make_anchor(private,policy,1)
   store=GenerationStore(path)
   store.stage(1,policy,anchor,sig)
   store.activate(1)
   pub=private.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw).hex()
   result=subprocess.run([sys.executable,'-c',CHILD,path,digest(anchor),'unused',pub],cwd=str(Path(__file__).resolve().parents[2]),capture_output=True,timeout=15)
   self.assertEqual(result.returncode,0,result.stderr.decode())
