import unittest
from scripts.audit_multisource_data import canonical_url, find_clusters, noise_reasons

class MultiSourceAuditTests(unittest.TestCase):
    def test_tracking_parameters_do_not_change_url_identity(self):
        self.assertEqual(canonical_url("HTTPS://WWW.Example.com/job/1/?utm_source=x&a=1"), "https://example.com/job/1?a=1")
    def test_near_duplicate_cross_source_jobs_share_cluster(self):
        text = "负责Python数据平台开发与维护，要求熟悉PostgreSQL、Docker和微服务架构。" * 5
        rows = [{"source_job_id":"a", "source_name":"A", "company":"甲公司", "standard_job_name":"数据工程师", "description":text},
                {"source_job_id":"b", "source_name":"B", "company":"甲公司", "standard_job_name":"数据工程师", "description":text + " 欢迎投递"}]
        clusters, pairs = find_clusters(rows)
        self.assertEqual(len(clusters), 1); self.assertTrue(pairs)
    def test_short_text_is_quarantined_with_reason(self):
        reasons = noise_reasons({"job_title":"投递", "description":"查看", "source_url":"bad"})
        self.assertIn("ui_noise_title", reasons); self.assertIn("invalid_source_url", reasons)

if __name__ == "__main__": unittest.main()
