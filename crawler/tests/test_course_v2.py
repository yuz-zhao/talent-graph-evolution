import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_course_v2 import validate

class CourseV2Test(unittest.TestCase):
    def test_formal_course_dataset(self):
        report = validate()
        self.assertTrue(report["passed"], report)
        self.assertGreaterEqual(report["formal_courses"], 700)

if __name__ == "__main__": unittest.main()
