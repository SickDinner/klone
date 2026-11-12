from io import BytesIO
from hashlib import sha256
import unittest

from klone.ingest_fingerprint import CHUNK_BYTES, fingerprint_stream, plan_ingest


class IngestFingerprintTests(unittest.TestCase):
    def test_streaming_large_synthetic_payload(self):
        data = b"x" * (CHUNK_BYTES * 3 + 7)
        result = fingerprint_stream(BytesIO(data))
        self.assertEqual(result.sha256, sha256(data).hexdigest())
        self.assertEqual(result.byte_length, len(data))
        self.assertEqual(result.chunk_count, 4)

    def test_duplicate_is_read_only(self):
        result = fingerprint_stream(BytesIO(b"synthetic"))
        self.assertEqual(plan_ingest(result, existing_hashes=frozenset()).action, "candidate")
        self.assertEqual(plan_ingest(result, existing_hashes=frozenset({result.sha256})).action, "duplicate")

    def test_limit_enforced(self):
        with self.assertRaisesRegex(ValueError, "ingest_size_limit"):
            fingerprint_stream(BytesIO(b"123456"), max_bytes=5)

    def test_nonbinary_stream_denied(self):
        from io import StringIO
        with self.assertRaisesRegex(ValueError, "binary_stream_required"):
            fingerprint_stream(StringIO("synthetic"))

    def test_invalid_limits_denied(self):
        for limit in (0, -1, True, 512 * 1024 * 1024 + 1):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    fingerprint_stream(BytesIO(b"x"), max_bytes=limit)


if __name__ == "__main__":
    unittest.main()
