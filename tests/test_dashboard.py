import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.config import ROOT


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Streamlit disponibile nel container')
class DashboardTests(unittest.TestCase):
    def test_three_pages_and_preferences(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'observatory.json'
            config.write_text((ROOT/'config/observatory.json').read_text())
            with patch.dict(os.environ,{'DATA_DIR':directory,'DB_PATH':directory+'/news.db','OBS_CONFIG':str(config)}):
                app=AppTest.from_file(str(ROOT/'dashboard/home.py')).run(timeout=20)
                self.assertEqual(len(app.exception),0)
                app.sidebar.radio[0].set_value('Archivio').run()
                self.assertEqual(len(app.exception),0)
                app.sidebar.radio[0].set_value('Impostazioni').run()
                self.assertEqual(len(app.exception),0)
                app.text_area[0].set_value('bioinformatics new tools')
                app.button[0].click().run()
                self.assertEqual(len(app.exception),0)
                self.assertIn('bioinformatics new tools',config.read_text())
