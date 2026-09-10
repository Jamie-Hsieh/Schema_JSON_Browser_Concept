import json
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from app import load_model, scope_ids, scoped, value_text
ROOT = Path(__file__).parent
class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / 'firstpass.json').read_bytes()
        self.data, self.index, self.warnings = load_model(self.raw)
    def test_real_extraction_and_scope(self):
        self.assertFalse(self.warnings)
        ids = scope_ids(self.data, 'part_system', True)
        self.assertIn('part_pump', ids)
        self.assertNotIn('part_supply', ids)
        self.assertTrue(all(a['owner_id'] in ids for a in scoped(self.data, 'attributes', ids)))
        self.assertEqual(value_text({'value_status': 'unknown'}), 'Unknown')
        self.assertEqual(value_text({'value_role':'range','lower_bound':0,'upper_bound':10,'unit':'V'}), '0 to 10 V')
    def test_invalid_input_and_cycle(self):
        with self.assertRaises(ValueError): load_model(b'{bad json')
        with self.assertRaises(ValueError): load_model(b'{"parts":[]}')
        d = json.loads(self.raw)
        d['parts'][0]['parent_id'] = d['parts'][0]['id']
        _, _, warnings = load_model(json.dumps(d).encode())
        self.assertTrue(any('cycle' in w for w in warnings))
    def test_views_and_empty_search(self):
        at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
        self.assertFalse(at.exception)
        for view in ['Parts','Attributes','Relationships','Requirements','Issues','Missing information','References']:
            at.radio[0].set_value(view).run()
            self.assertFalse(at.exception, view)
            self.assertTrue(at.dataframe, view)
        at.sidebar.selectbox[0].set_value('part_motor').run()
        at.radio[0].set_value('Attributes').run()
        self.assertFalse(at.exception)
        at.sidebar.text_input[0].set_value('no_match_928393820').run()
        self.assertFalse(at.exception)
        self.assertTrue(any('No matching' in i.value for i in at.info))
if __name__ == '__main__': unittest.main()
