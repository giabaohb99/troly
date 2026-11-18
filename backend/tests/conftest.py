import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def use_test_database():
    """Chỉ chạy trên DB có tên kết thúc bằng _test để không đụng DB thật."""
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        pytest.exit("TEST_DATABASE_URL phải trỏ tới DB có tên kết thúc bằng _test.", returncode=2)
    os.environ["DATABASE_URL"] = url
    yield
