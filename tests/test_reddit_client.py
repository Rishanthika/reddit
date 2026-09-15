"""
Tests for the Apify-based Reddit collector (app/reddit_client.py).

No real Apify API calls are made — `ApifyClient` is replaced with an
in-memory fake that mimics the two calls RedditClient actually uses:
`.actor(id).call(run_input=...)` and `.dataset(id).list_items()`.
"""

from datetime import timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.reddit_client import RedditClient, RedditClientError, RedditPost


class _FakeListItemsResult:
    def __init__(self, items):
        self.items = items


class _FakeDatasetClient:
    def __init__(self, items):
        self._items = items

    def list_items(self):
        return _FakeListItemsResult(self._items)


class _FakeActorClient:
    def __init__(self, run_result, raise_on_call=None):
        self._run_result = run_result
        self._raise_on_call = raise_on_call
        self.last_run_input = None

    def call(self, run_input=None):
        self.last_run_input = run_input
        if self._raise_on_call:
            raise self._raise_on_call
        return self._run_result


_UNSET = object()


class _FakeApifyClient:
    """Stand-in for apify_client.ApifyClient — never touches the network."""

    def __init__(self, items, run_result=_UNSET, raise_on_call=None, raise_on_dataset=None):
        self._items = items
        self._run_result = (
            SimpleNamespace(default_dataset_id="dataset-1") if run_result is _UNSET else run_result
        )
        self._raise_on_call = raise_on_call
        self._raise_on_dataset = raise_on_dataset
        self.actor_client = _FakeActorClient(self._run_result, raise_on_call)

    def actor(self, actor_id):
        return self.actor_client

    def dataset(self, dataset_id):
        if self._raise_on_dataset:
            raise self._raise_on_dataset
        return _FakeDatasetClient(self._items)


def _make_client(items, **kwargs) -> RedditClient:
    fake = _FakeApifyClient(items, **kwargs)
    with patch("app.reddit_client.ApifyClient", return_value=fake):
        client = RedditClient(
            apify_api_token="fake-token",
            actor_id="automation-lab/reddit-scraper",
            subreddits=["studyabroad", "gradadmissions"],
        )
    return client


def _post_item(**overrides):
    base = {
        "type": "post",
        "id": "abc123",
        "title": "I want to do MS in Germany",
        "author": "example_user",
        "subreddit": "studyabroad",
        "createdAt": "2026-09-01T12:00:00.000Z",
        "url": "https://www.reddit.com/r/studyabroad/comments/abc123/",
        "permalink": "/r/studyabroad/comments/abc123/i_want_to_do_ms_in_germany/",
        "selfText": "Which universities should I apply to?",
    }
    base.update(overrides)
    return base


def test_maps_apify_record_to_reddit_post():
    client = _make_client([_post_item()])

    posts = list(client.fetch_new_posts(limit=25))

    assert len(posts) == 1
    post = posts[0]
    assert isinstance(post, RedditPost)
    assert post.reddit_post_id == "abc123"
    assert post.username == "u/example_user"
    assert post.subreddit == "studyabroad"
    assert post.title == "I want to do MS in Germany"
    assert post.post_text == "Which universities should I apply to?"
    assert post.post_url.startswith("https://www.reddit.com/r/studyabroad/comments/abc123")
    assert post.created_at.tzinfo is not None
    assert post.created_at.astimezone(timezone.utc).year == 2026


def test_empty_self_text_falls_back_to_title_only():
    client = _make_client([_post_item(selfText="")])

    posts = list(client.fetch_new_posts(limit=25))

    assert len(posts) == 1
    assert posts[0].post_text == ""
    assert posts[0].title == "I want to do MS in Germany"


def test_deleted_author_becomes_deleted_placeholder():
    client = _make_client([_post_item(author=None)])

    posts = list(client.fetch_new_posts(limit=25))

    assert posts[0].username == "[deleted]"


def test_posts_outside_allowlist_are_filtered_out():
    client = _make_client(
        [
            _post_item(id="a1", subreddit="studyabroad"),
            _post_item(id="a2", subreddit="unrelated_subreddit"),
        ]
    )

    posts = list(client.fetch_new_posts(limit=25))

    assert [p.reddit_post_id for p in posts] == ["a1"]


def test_comment_type_records_are_ignored():
    client = _make_client(
        [
            _post_item(id="a1"),
            {"type": "comment", "id": "c1", "subreddit": "studyabroad", "body": "hi"},
        ]
    )

    posts = list(client.fetch_new_posts(limit=25))

    assert [p.reddit_post_id for p in posts] == ["a1"]


def test_malformed_record_is_skipped_not_raised():
    client = _make_client(
        [
            _post_item(id="a1"),
            _post_item(id=None),  # missing usable id -> should be skipped, not crash
        ]
    )

    posts = list(client.fetch_new_posts(limit=25))

    assert [p.reddit_post_id for p in posts] == ["a1"]


def test_duplicate_ids_in_one_run_are_deduplicated():
    client = _make_client([_post_item(id="a1"), _post_item(id="a1")])

    posts = list(client.fetch_new_posts(limit=25))

    assert len(posts) == 1


def test_empty_dataset_returns_no_posts():
    client = _make_client([])

    posts = list(client.fetch_new_posts(limit=25))

    assert posts == []


def test_actor_call_failure_raises_reddit_client_error():
    client = _make_client([], raise_on_call=RuntimeError("actor boom"))

    try:
        list(client.fetch_new_posts(limit=25))
        assert False, "expected RedditClientError"
    except RedditClientError:
        pass


def test_missing_dataset_id_raises_reddit_client_error():
    # apify-client's Run model always has a `default_dataset_id` attribute,
    # but guard against a run that didn't finish/populate it (e.g. None).
    client = _make_client([], run_result=SimpleNamespace(default_dataset_id=None))

    try:
        list(client.fetch_new_posts(limit=25))
        assert False, "expected RedditClientError"
    except RedditClientError:
        pass


def test_none_run_raises_reddit_client_error():
    # `.actor(id).call(...)` is typed to return `Run | None`.
    client = _make_client([], run_result=None)

    try:
        list(client.fetch_new_posts(limit=25))
        assert False, "expected RedditClientError"
    except RedditClientError:
        pass


def test_run_input_uses_new_sort_and_no_comments():
    fake = _FakeApifyClient([_post_item()])
    with patch("app.reddit_client.ApifyClient", return_value=fake):
        client = RedditClient(
            apify_api_token="fake-token",
            actor_id="automation-lab/reddit-scraper",
            subreddits=["studyabroad", "gradadmissions"],
        )
        list(client.fetch_new_posts(limit=25))

    run_input = fake.actor_client.last_run_input
    assert run_input["sort"] == "new"
    assert run_input["includeComments"] is False
    assert run_input["maxPostsPerSource"] == 25
    assert "filterKeywords" not in run_input
    assert "outputFormat" not in run_input
    assert set(run_input["urls"]) == {
        "https://www.reddit.com/r/studyabroad/",
        "https://www.reddit.com/r/gradadmissions/",
    }
