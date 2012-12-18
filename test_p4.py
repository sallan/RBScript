from unittest import TestCase
import mock

from rb import P4

class TestP4(TestCase):

    def setUp(self):
        self.p4 = P4()

    def test_list_shelves(self):
        expected = ['123', '678']
        actual = self.p4.list_shelves()
        self.assertEqual(expected, actual)
