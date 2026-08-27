import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_job_standard_dict_v2 import validate
class JobStandardV2Test(unittest.TestCase):
 def test_quality_gate(self):self.assertTrue(validate()['passed'])
if __name__=='__main__':unittest.main()
