import unittest

from lk_textbooks import _utils


class TestCase(unittest.TestCase):
    def test_log(self):
        self.assertTrue(_utils.log is not None)


if __name__ == '__main__':
    unittest.main()
