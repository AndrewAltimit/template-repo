"""Checkpoint stores: key validation, the local backend, and the S3 backend against a fake client."""

import io

import pytest

from recurrent_depth import store


@pytest.mark.parametrize("key", ["", "/abs", "a//b", "a/../b", "..", "./a", "a\\b", "a/./b", "x\x00y"])
def test_bad_keys_refused(key):
    with pytest.raises(ValueError):
        store.validate_key(key)


def test_local_store_roundtrip(tmp_path):
    s = store.LocalStore(tmp_path / "s")
    src = tmp_path / "f.txt"
    src.write_text("hello")
    s.put_file(src, "runs/r1/stages/a/f.txt")
    s.put_bytes("runs/r1/manifest.json", b"{}")
    assert s.exists("runs/r1/stages/a/f.txt")
    assert not s.exists("runs/r1/missing")
    assert s.get_bytes("runs/r1/manifest.json") == b"{}"
    assert s.get_bytes("nope") is None
    assert s.keys("runs/r1") == ["runs/r1/manifest.json", "runs/r1/stages/a/f.txt"]
    assert s.keys("runs/none") == []
    dest = tmp_path / "out" / "g.txt"
    assert s.get_file("runs/r1/stages/a/f.txt", dest) and dest.read_text() == "hello"
    assert not s.get_file("missing", tmp_path / "x")


def test_local_store_cannot_escape(tmp_path):
    s = store.LocalStore(tmp_path / "s")
    with pytest.raises(ValueError):
        s.put_bytes("../escape", b"x")
    assert not (tmp_path / "escape").exists()


class _NotFound(Exception):
    response = {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}}


class FakeS3:
    """Enough of the boto3 S3 client for S3Store, with paginated listing."""

    def __init__(self, page=2):
        self.objects = {}
        self.page = page

    def upload_file(self, local, bucket, key):
        with open(local, "rb") as f:
            self.objects[(bucket, key)] = f.read()

    def download_file(self, bucket, key, local):
        with open(local, "wb") as f:
            f.write(self.objects[(bucket, key)])

    def put_object(self, Bucket, Key, Body):  # noqa: N803 - boto3 argument names
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        if (Bucket, Key) not in self.objects:
            raise _NotFound()
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, Bucket, Key):  # noqa: N803
        if (Bucket, Key) not in self.objects:
            raise _NotFound()
        return {}

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):  # noqa: N803
        keys = sorted(k for b, k in self.objects if b == Bucket and k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        chunk = keys[start : start + self.page]
        more = start + self.page < len(keys)
        resp = {"Contents": [{"Key": k} for k in chunk], "IsTruncated": more}
        if more:
            resp["NextContinuationToken"] = str(start + self.page)
        return resp


def test_s3_store_with_prefix_and_pagination(tmp_path):
    fake = FakeS3(page=2)
    s = store.S3Store("bucket", "campaigns/", client=fake)
    assert s.uri == "s3://bucket/campaigns/"
    for i in range(5):
        s.put_bytes(f"runs/r1/f{i}", str(i).encode())
    assert ("bucket", "campaigns/runs/r1/f0") in fake.objects
    assert s.keys("runs/r1") == [f"runs/r1/f{i}" for i in range(5)]
    assert s.get_bytes("runs/r1/f3") == b"3"
    assert s.get_bytes("runs/r1/missing") is None
    assert s.exists("runs/r1/f4") and not s.exists("runs/r2/f4")
    src = tmp_path / "a.bin"
    src.write_bytes(b"abc")
    s.put_file(src, "runs/r1/a.bin")
    out = tmp_path / "d" / "a.bin"
    assert s.get_file("runs/r1/a.bin", out) and out.read_bytes() == b"abc"


def test_s3_store_propagates_other_errors():
    class Denied(Exception):
        response = {"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}}

    class Client(FakeS3):
        def head_object(self, Bucket, Key):  # noqa: N803
            raise Denied()

    with pytest.raises(Denied):
        store.S3Store("b", client=Client()).exists("k")


def test_open_store(tmp_path):
    assert isinstance(store.open_store(str(tmp_path / "x")), store.LocalStore)
    assert isinstance(store.open_store((tmp_path / "y").as_uri()), store.LocalStore)
    with pytest.raises(ValueError):
        store.open_store("ftp://host/x")
    with pytest.raises(ValueError):
        store.S3Store("bad/bucket", client=FakeS3())
