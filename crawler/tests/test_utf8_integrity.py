import unittest

from crawler.utils.encoding_quality import mojibake_matches


class Utf8IntegrityTest(unittest.TestCase):
    def test_clean_chinese_is_accepted(self):
        self.assertEqual(mojibake_matches("负责机器学习、知识图谱和数据治理"), [])

    def test_common_corruption_is_rejected(self):
        for text in ("绠楁硶优化", "ObtÃ©n visibilidad", "AI agentsâcorrelated", "坏字符�"):
            self.assertTrue(mojibake_matches(text), text)


if __name__ == "__main__":
    unittest.main()
