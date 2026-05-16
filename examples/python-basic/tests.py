import unittest


class DeterministicTests(unittest.TestCase):
    def test_addition_is_stable(self) -> None:
        self.assertEqual(2 + 2, 4)

    def test_sorted_is_deterministic(self) -> None:
        self.assertEqual(sorted("dcba"), ["a", "b", "c", "d"])


if __name__ == "__main__":
    unittest.main()
