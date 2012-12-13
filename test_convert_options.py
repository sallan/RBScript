#!/usr/bin/python
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

    def test_diff_only(self):
        opts, args = self.options_parser.parse_args(["-n"])
        self.assertEqual("--output-diff", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--output-diff"])
        self.assertEqual("--output-diff", convert_options(opts))

    def test_open(self):
        opts, args = self.options_parser.parse_args(["-o"])
        self.assertEqual("--open", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--open"])
        self.assertEqual("--open", convert_options(opts))

    def test_publish(self):
        opts, args = self.options_parser.parse_args(["--publish"])
        self.assertEqual("--publish", convert_options(opts))

    def test_server(self):
        opts, args = self.options_parser.parse_args(["--server" , "https://foo.bar.com"])
        self.assertEqual("--server https://foo.bar.com", convert_options(opts))

    def test_changeset(self):
        opts, args = self.options_parser.parse_args(["-c", "12345"])
        self.assertEqual("12345", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--change", "12345"])
        self.assertEqual("12345", convert_options(opts))

    def test_people(self):
        opts, args = self.options_parser.parse_args(["-u", "'user1, user2'"])
        self.assertEqual("--target-people 'user1, user2'", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--target-people", "'user1, user2'"])
        self.assertEqual("--target-people 'user1, user2'", convert_options(opts))

    def test_groups(self):
        opts, args = self.options_parser.parse_args(["-g", "'grp1, grp2'"])
        self.assertEqual("--target-groups 'grp1, grp2'", convert_options(opts))
        opts, args = self.options_parser.parse_args(["--target-groups", "'grp1, grp2'"])
        self.assertEqual("--target-groups 'grp1, grp2'", convert_options(opts))

    def test_submit_as(self):
        opts, args = self.options_parser.parse_args(["--submit-as", "hacker_supreme"])
        self.assertEqual("--submit-as hacker_supreme", convert_options(opts))

