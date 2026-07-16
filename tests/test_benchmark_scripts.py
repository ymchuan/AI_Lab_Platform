import unittest
from pathlib import Path


class BenchmarkScriptTest(unittest.TestCase):
    def test_8060s_smoke_script_is_ascii_for_windows_powershell(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "benchmarks"
            / "run_8060s_brain_smoke.ps1"
        )

        text = script.read_bytes().decode("ascii")
        self.assertIn("ErrorDetails.Message", text)
        self.assertIn('$evaluatedResults', text)
        self.assertIn('[Parameter(Mandatory = $true)]', text)
        self.assertIn('skipped_after_fatal', text)
        self.assertIn('-MinimalRequest', text)
        self.assertIn('Test-FatalRuntimeError', text)
        self.assertNotIn('$md.Add("- `', text)


if __name__ == "__main__":
    unittest.main()
