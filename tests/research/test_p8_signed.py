import os,tempfile,unittest,sqlite3
from contextlib import closing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from research.ab_snapshot.p8_generations import GenerationStore,PublicationError,digest
from research.ab_snapshot.p7_publication import make_anchor,check_publication,PublicationError as P7Error
from research.ab_snapshot.validator import canonical
class SignedIntegration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=GenerationStore(os.path.join(self.tmp.name,'store.db'))
  self.key=Ed25519PrivateKey.generate();self.p=canonical({'version':1});self.a,self.sig=make_anchor(self.key,self.p,1)
  self.store.stage(1,self.p,self.a,self.sig);self.store.activate(1)
 def verify(self,expected=None):
  return self.store.read(1,expected or digest(self.a),lambda p,a,s:check_publication(p,a,s,self.key.public_key(),expected or digest(self.a)))
 def test_signed_success(self):self.assertEqual(self.verify(),1)
 def test_tampered_signature(self):
  with closing(sqlite3.connect(self.store.path)) as db,db:db.execute('UPDATE generations SET signature=?',(b'0'*64,))
  with self.assertRaisesRegex(P7Error,'E701_PUBLICATION_INVALID'):self.verify()
 def test_policy_tamper(self):
  with closing(sqlite3.connect(self.store.path)) as db,db:db.execute('UPDATE generations SET policy=?',(canonical({'version':9}),))
  with self.assertRaisesRegex(P7Error,'E702_POLICY_ANCHOR_MISMATCH'):self.verify()
 def test_consistent_rollback(self):
  p2=canonical({'version':2});a2,s2=make_anchor(self.key,p2,2)
  self.store.stage(2,p2,a2,s2);self.store.activate(2)
  with closing(sqlite3.connect(self.store.path)) as db,db:db.execute('UPDATE active SET generation=1')
  with self.assertRaisesRegex(PublicationError,'E804_EXTERNAL_VERSION_MISMATCH'):
   self.store.read(2,digest(a2),lambda p,a,s:check_publication(p,a,s,self.key.public_key(),digest(a2)))
