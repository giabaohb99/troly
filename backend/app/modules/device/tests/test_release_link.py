"""Lỗi thật 25/11: link APK ký sẵn 300 giây hết hạn trước khi người dùng bấm cập nhật. Link bản phát hành sống
30 phút; trang /tai-app trỏ tới /tai-app/apk, route này ký link mới mỗi lần bấm."""

import json
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from moto import mock_aws

from app.core import storage
from app.core.config import get_settings
from app.modules.device import service

LATEST = {
    "version_code": 110,
    "version_name": "1.1.0",
    "apk_key": "releases/troly-1.1.0.apk",
    "sha256": "abc123",
    "size_bytes": 6_000_000,
    "min_supported_version_code": 100,
}


@pytest.fixture
def release(monkeypatch):
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = get_settings().r2_bucket
        s3.create_bucket(Bucket=bucket)
        s3.put_object(Bucket=bucket, Key=service.LATEST_KEY, Body=json.dumps(LATEST).encode())
        monkeypatch.setattr(storage, "_client", lambda: s3)
        # Bộ đệm latest.json: khôi phục cả mốc lẫn giá trị sau bài, kẻo bài sau thấy bản phát hành mẫu.
        monkeypatch.setitem(service._cache, "at", 0.0)
        monkeypatch.setitem(service._cache, "value", None)
        real = storage.presign_get
        signed: list[int | None] = []

        def spy(bucket, key, filename=None, expires=None):
            signed.append(expires)
            return (
                real(bucket, key, filename, expires) + f"&ttl={expires or get_settings().r2_presign_seconds}"
            )

        monkeypatch.setattr(storage, "presign_get", spy)
        yield signed


def _expires(url: str) -> int:
    return int(parse_qs(urlparse(url).query)["ttl"][0])


def test_release_link_lives_30_minutes(auth_client, release):
    latest = auth_client.get("/api/v1/device/release", params={"current_version_code": 105}).json()["data"]
    assert latest["update_available"] and latest["latest"]["download_expires_in"] == 1800
    assert _expires(latest["latest"]["download_url"]) == 1800
    other = storage.presign_get(get_settings().r2_bucket, "files/u/1/x")
    assert _expires(other) == get_settings().r2_presign_seconds == 300  # link tệp thường giữ 5 phút


def test_download_page_points_to_fresh_redirect(client, release):
    page = client.get("/tai-app")
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    assert 'href="/tai-app/apk"' in page.text and "X-Amz" not in page.text  # trang không chứa link sẽ hết hạn
    first = client.get("/tai-app/apk", follow_redirects=False)
    assert first.status_code == 302 and first.headers["cache-control"] == "no-store"
    assert "troly-1.1.0.apk" in first.headers["location"] and _expires(first.headers["location"]) == 1800


def test_download_redirect_404_without_release(client, monkeypatch):
    monkeypatch.setattr(service, "latest_release", lambda: None)
    assert client.get("/tai-app/apk", follow_redirects=False).status_code == 404
    assert "Chưa có bản phát hành" in client.get("/tai-app").text
