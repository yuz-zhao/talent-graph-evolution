from crawler.spiders.tech.github_trend_spider import TARGET_FIELDS, legacy_record, repo_record
from crawler.spiders.tech.gitee_trend_spider import normalize as normalize_gitee


def sample_github():
    return {
        "id": 123, "full_name": "owner/repo", "name": "repo",
        "owner": {"login": "owner"}, "description": None,
        "html_url": "https://github.com/owner/repo", "homepage": None,
        "created_at": "2024-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "pushed_at": "2025-12-31T00:00:00Z", "language": "Python", "topics": ["iot"],
        "license": None, "archived": False, "fork": False,
        "stargazers_count": 10, "forks_count": 2, "open_issues_count": 1,
        "watchers_count": 10, "default_branch": "main",
    }


def test_github_target_schema_and_api_values():
    row = repo_record(sample_github(), "2026-08-02T00:00:00Z")
    assert list(row) == TARGET_FIELDS
    assert row["repo_id"] == "123"
    assert row["stars"] == 10
    assert row["license"] == ""
    assert row["created_at"] != row["updated_at"]


def test_legacy_retains_url_but_does_not_invent_metrics():
    row = legacy_record({
        "tech_name": "repo", "source_url": "https://github.com/owner/repo",
        "summary": "old", "tags": ["ai"], "crawl_time": "2026-06-01",
        "hot_score": 0.8,
    })
    assert row["html_url"] == "https://github.com/owner/repo"
    assert row["repo_id"] == ""
    assert row["stars"] == row["forks"] == ""


def test_gitee_is_normalized_as_separate_source():
    row = normalize_gitee({
        "id": 9, "full_name": "rtthread/rt-thread", "name": "rt-thread",
        "owner": {"login": "rtthread"}, "html_url": "https://gitee.com/rtthread/rt-thread",
        "stargazers_count": 5, "forks_count": 1, "watchers_count": 2,
        "open_issues_count": 3,
    }, "物联网/嵌入式", "2026-08-02T00:00:00Z")
    assert row["source"] == "gitee_api"
    assert row["category"] == "物联网/嵌入式"
    assert row["stars"] == 5
