import hashlib
import subprocess
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from compressor import ENTRY_FORMAT, HEADER_FORMAT, compress
from decompressor import decompress


class CodecTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)

    def _roundtrip(self, name, data):
        source = self.directory / name
        archive = self.directory / f"{name}.tdi"
        output = self.directory / f"{name}.out"
        source.write_bytes(data)

        with redirect_stdout(StringIO()):
            compress(str(source), str(archive), verbose=False)
            decompress(str(archive), str(output), verbose=False)

        self.assertEqual(output.read_bytes(), data)
        self.assertEqual(
            hashlib.sha256(output.read_bytes()).digest(),
            hashlib.sha256(data).digest(),
        )
        return archive

    def test_course_corpus_roundtrips(self):
        test_directory = Path(__file__).parent
        for source in sorted(test_directory.glob("prueba_*.txt")):
            with self.subTest(source=source.name):
                self._roundtrip(source.name, source.read_bytes())

    def test_empty_odd_and_even_inputs_roundtrip(self):
        for name, data in (
            ("empty", b""),
            ("odd", b"\x00\xff\x00"),
            ("even", b"\xff\x00\xff\x00"),
        ):
            with self.subTest(name=name):
                self._roundtrip(name, data)

    def test_all_65536_byte_pairs_roundtrip(self):
        data = b"".join(pair.to_bytes(2, "big") for pair in range(65536))
        self._roundtrip("all_pairs", data)

    def test_payload_bitflip_is_rejected_before_output(self):
        archive = self._roundtrip("corrupt", b"ABACABAD" * 64)
        packed = bytearray(archive.read_bytes())
        header_size = struct.calcsize(HEADER_FORMAT)
        entry_count_offset = 4 + struct.calcsize(">QQB")
        (entry_count,) = struct.unpack(
            ">I", packed[entry_count_offset:entry_count_offset + 4]
        )
        payload_offset = 4 + header_size + entry_count * struct.calcsize(ENTRY_FORMAT)
        packed[payload_offset] ^= 1

        corrupted = self.directory / "corrupted.tdi"
        output = self.directory / "corrupted.out"
        corrupted.write_bytes(packed)
        with self.assertRaises(ValueError):
            decompress(str(corrupted), str(output), verbose=False)
        self.assertFalse(output.exists())

    def test_truncated_archive_is_rejected_before_output(self):
        archive = self._roundtrip("truncated", b"round-trip data" * 16)
        truncated = self.directory / "short.tdi"
        output = self.directory / "short.out"
        truncated.write_bytes(archive.read_bytes()[:-1])

        with self.assertRaises(ValueError):
            decompress(str(truncated), str(output), verbose=False)
        self.assertFalse(output.exists())

    def test_cli_returns_nonzero_for_truncated_archive(self):
        archive = self._roundtrip("cli-truncated", b"payload" * 64)
        truncated = self.directory / "cli-short.tdi"
        output = self.directory / "cli-short.out"
        truncated.write_bytes(archive.read_bytes()[:-1])
        script = Path(__file__).parent.parent / "decompressor.py"

        result = subprocess.run(
            [sys.executable, str(script), str(truncated), str(output)],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error:", result.stderr)
        self.assertFalse(output.exists())

    def test_input_and_output_paths_must_differ(self):
        source = self.directory / "same-path.bin"
        source.write_bytes(b"do not overwrite")
        with self.assertRaises(ValueError):
            compress(str(source), str(source), verbose=False)


if __name__ == "__main__":
    unittest.main()
