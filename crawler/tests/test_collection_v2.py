import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_collection_v2 import main
class CollectionV2Test(unittest.TestCase):
 def test_pipeline(self):self.assertEqual(main(),0)
if __name__=='__main__':unittest.main()
