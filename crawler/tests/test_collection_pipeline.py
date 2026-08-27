import json
import tempfile
import unittest
from pathlib import Path

from crawler.utils.collection_pipeline import CollectionStore, content_hash, load_records


class CollectionPipelineTest(unittest.TestCase):
    def test_insert_unchanged_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CollectionStore(tmp)
            record = {
                "title": "AI Engineer",
                "summary": "Python and RAG",
                "source_url": "https://example.com/jobs/1",
                "publish_time": "2026-08-01",
            }
            first = store.ingest("example", "job", [record])
            self.assertEqual(first.inserted, 1)
            second = store.ingest("example", "job", [record])
            self.assertEqual(second.unchanged, 1)
            changed = dict(record, summary="Python, RAG and GraphRAG")
            third = store.ingest("example", "job", [changed])
            self.assertEqual(third.updated, 1)
            self.assertEqual(third.changed_records, 1)
            batch = next((Path(tmp) / ".ops" / "collection" / "batches").glob(f"{third.batch_id}.jsonl"))
            item = json.loads(batch.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(item["changed_fields"][0]["field"], "summary")

    def test_complete_snapshot_marks_missing_then_expired_and_reopened(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CollectionStore(tmp)
            record = {"job_title": "AI Engineer", "source_url": "https://example.com/1"}
            store.ingest("example", "job", [record], complete_snapshot=True)
            first_missing = store.ingest("example", "job", [], complete_snapshot=True)
            self.assertEqual(first_missing.suspected_missing, 1)
            second_missing = store.ingest("example", "job", [], complete_snapshot=True)
            self.assertEqual(second_missing.expired, 1)
            reopened = store.ingest("example", "job", [record], complete_snapshot=True)
            self.assertEqual(reopened.reopened, 1)

    def test_crawl_time_does_not_change_content_hash(self):
        a = {"title": "A", "crawl_time": "2026-01-01"}
        b = {"title": "A", "crawl_time": "2026-08-01"}
        self.assertEqual(content_hash(a), content_hash(b))

    def test_repository_uses_repo_id_and_html_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CollectionStore(tmp)
            first = {
                "repo_id": "123", "full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo",
                "description": "first", "created_at": "2024-01-01T00:00:00Z",
                "observed_at": "2026-08-01T00:00:00Z",
            }
            second = dict(first, description="changed", observed_at="2026-08-08T00:00:00Z")
            inserted = store.ingest("github", "technology_project", [first])
            updated = store.ingest("github", "technology_project", [second])
            self.assertEqual(inserted.inserted, 1)
            self.assertEqual(updated.updated, 1)
            self.assertEqual(inserted.missing_url, 0)

    def test_reject_empty_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = CollectionStore(tmp).ingest("example", "job", [{}])
            self.assertEqual(report.rejected, 1)
            self.assertEqual(report.valid, 0)
            self.assertEqual(report.quality()["source_url_coverage"], 0)
            self.assertEqual(report.quality()["content_coverage"], 0)

    def test_jsonl_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.jsonl"
            path.write_text(json.dumps({"title": "A"}) + "\n", encoding="utf-8")
            self.assertEqual(load_records(path), [{"title": "A"}])

    def test_batch_quality_uses_original_input_and_writes_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CollectionStore(tmp)
            valid = {"title": "AI Engineer", "summary": "Python", "source_url": "https://example.com/1"}
            failures = [{"stage": "validate", "reason": "required_field_missing", "record_index": 1, "missing_fields": ["source_url"]}]
            report = store.ingest("example", "job", [valid], fetched_count=2,
                                  pipeline_failures=failures,
                                  stage_counts={"parsed": 2, "normalized": 2, "validated": 1})
            self.assertEqual(report.fetched, 2)
            self.assertEqual(report.rejected, 1)
            self.assertEqual(report.quality()["source_url_coverage"], 0.5)
            self.assertEqual(report.quality()["validity_rate"], 0.5)
            failure_path = Path(tmp) / report.failure_path
            self.assertTrue(failure_path.exists())
            failure = json.loads(failure_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(failure["batch_id"], report.batch_id)
            self.assertEqual(failure["reason"], "required_field_missing")

    def test_duplicate_in_same_batch_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = {"title": "AI Engineer", "summary": "Python", "source_url": "https://example.com/1"}
            report = CollectionStore(tmp).ingest("example", "job", [record, dict(record)])
            self.assertEqual(report.inserted, 1)
            self.assertEqual(report.duplicate_in_batch, 1)
            self.assertEqual(report.rejected, 1)
            self.assertEqual(report.quality()["uniqueness_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
