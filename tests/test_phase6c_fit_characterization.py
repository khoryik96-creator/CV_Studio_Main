import os
from pathlib import Path
import tempfile
import unittest
from owner_build_tools import build_protected

_TEMP=tempfile.TemporaryDirectory(prefix="cvstudio-phase6c-")
_ROOT=Path(__file__).resolve().parents[1]
os.environ["CVSTUDIO_DB_PATH"]=str(Path(_TEMP.name)/"state.sqlite3")
os.environ["LOCALAPPDATA"]=str(Path(_TEMP.name)/"local")
build_protected.write_test_receipt(_ROOT)
import app

class Phase6CFitCharacterizationTests(unittest.TestCase):
    def test_native_boolean_floor_is_explained_without_changing_score(self):
        candidate={"_spiderNativeBooleanMatched":True,"_spiderBooleanRule":"Python","name":"Fixture"}
        score,evidence,unknown,breakdown=app._spider_match_fit_percent(candidate,{"must":"Python"},"fixture has no matching skill",["Python"])
        self.assertEqual(score,60)
        self.assertEqual(breakdown["final_percent"],60)
        row=breakdown["components"][0]
        self.assertTrue(row["native_boolean_floor"])
        self.assertEqual(row["coverage_before_adjustment_percent"],0)
        self.assertEqual(row["points_before_adjustment"],0.0)
        self.assertEqual(row["evidence_status"],"unavailable")
        self.assertIn("JobAdder confirmed",evidence[0])

    def test_discovery_floor_and_component_inputs_remain_exact(self):
        score,evidence,unknown,breakdown=app._spider_match_fit_percent({}, {"role":"Python"}, "no relevant evidence", ["discovered"])
        self.assertEqual(score,10)
        self.assertEqual(breakdown["raw_percent"],0)
        self.assertTrue(breakdown["discovery_floor_applied"])
        self.assertEqual(breakdown["components"][0]["evidence_status"],"unavailable")
        self.assertTrue(any("visible job-fit evidence is limited" in item for item in unknown))

if __name__=='__main__': unittest.main()
