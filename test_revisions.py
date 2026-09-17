import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from app import load_model,revision_family
ROOT=Path(__file__).parent

def example():
 d=json.loads((ROOT/'firstpass.json').read_text());d['schema_version']='1.3'
 for a in d['attributes']:a.update(record_status='current',supersedes_id=None)
 old=d['attributes'][0];old['record_status']='superseded'
 new=copy.deepcopy(old);new.update(id='attr_test_replacement',record_status='current',supersedes_id=old['id'],value=555);d['attributes'].append(new)
 for c in d['expected_information_check']:
  if c['attribute_id']==old['id']:c['attribute_id']=new['id']
 return d
class RevisionTests(unittest.TestCase):
 def test_history_and_bad_links(self):
  d=example();_,index,warnings=load_model(json.dumps(d).encode());self.assertFalse(warnings)
  self.assertEqual(len(revision_family('attr_test_replacement',index)),2)
  d['attributes'][-1]['supersedes_id']='attr_missing'
  self.assertTrue(any('does not reference' in w for w in load_model(json.dumps(d).encode())[2]))
  d=example();d['attributes'][0]['supersedes_id']='attr_test_replacement'
  self.assertTrue(any('cycle' in w for w in load_model(json.dumps(d).encode())[2]))
 def test_views(self):
  original=Path.read_bytes;raw=json.dumps(example()).encode()
  def read(p):return raw if p.name=='firstpass.json' else original(p)
  with patch.object(Path,'read_bytes',read):
   at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();self.assertFalse(at.exception)
   at.radio[0].set_value('Attributes').run();self.assertFalse(at.exception)
   self.assertEqual(at.radio[1].value,'Current')
   at.radio[1].set_value('Superseded').run();self.assertFalse(at.exception)
   self.assertEqual(len(at.dataframe[0].value),1)
   at.radio[0].set_value('Revision history').run();self.assertFalse(at.exception)
if __name__=='__main__':unittest.main()
