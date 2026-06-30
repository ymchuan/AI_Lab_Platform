import unittest

from app import add, format_total


class AppTest(unittest.TestCase):
    def test_add(self) -> None:
        self.assertEqual(add(2, 3), 5)

    def test_format_total(self) -> None:
        self.assertEqual(format_total([1, 2, 3]), "total=6")


if __name__ == "__main__":
    unittest.main()
