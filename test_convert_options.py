from unittest import TestCase
from rb import convert_options
from rb import parse_options

class TestConvert_options(TestCase):
    def setUp(self):
        self.options_parser = parse_options()


    def test_none(self):
        opts, args = self.options_parser.parse_args()
        self.assertEqual("", convert_options(opts))

    def test_debug(self):
        opts, args = self.options_parser.parse_args(["-d"])
        self.assertEqual("--debug", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--debug"])
        self.assertEqual("--debug", convert_options(opts))

    def test_server(self):
        opts, args = self.options_parser.parse_args(["--server" , "https://foo.bar.com"])
        self.assertEqual("--server https://foo.bar.com", convert_options(opts))

    def test_changeset(self):
        opts, args = self.options_parser.parse_args(["-c", "12345"])
        self.assertEqual("12345", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--changeset", "12345"])
        self.assertEqual("12345", convert_options(opts))

    def test_bug(self):
        opts, args = self.options_parser.parse_args(["-b", "BZ666"])
        self.assertEqual("--bugs-closed BZ666", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--bug", "BZ666"])
        self.assertEqual("--bugs-closed BZ666", convert_options(opts))

    def test_bug(self):
        opts, args = self.options_parser.parse_args(["-g", "'grp1, grp2'"])
        self.assertEqual("--target-groups 'grp1, grp2'", convert_options(opts))

        