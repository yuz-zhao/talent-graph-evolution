import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from validate_certificate_v2 import validate
class CertificateV2Test(unittest.TestCase):
    def test_verified_certificates(self): self.assertTrue(validate()["passed"])
if __name__=="__main__": unittest.main()
