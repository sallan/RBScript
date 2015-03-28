#!/usr/bin/python

from unittest import TestCase
from unittest import main

import p2


class TestOpt_parser(TestCase):
    def test_opt_parser(self):
        test_args = ['edit', '--debug', '999']
        action, args = p2.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--debug', '999'])

        test_args = ['edit', '999', '--debug']
        action, args = p2.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--debug', '999'])

        test_args = ['create', '999', '--server', 'http://rb', '999', '--debug', '999']
        action, args = p2.parse_options(test_args)
        self.assertEqual("create", action)
        self.assertEqual(args, ['rbt', 'create', '--server', 'http://rb', '--debug', '999'])

        test_args = ['edit', '--shelve', '999', '--server', 'http://rb', '999', '--debug', '999']
        action, args = p2.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--shelve', '--server', 'http://rb', '--debug', '999'])

        test_args = ['edit', '999', '--publish']
        action, args = p2.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--publish', '999'])


class TestFindBugs(TestCase):
    change_list = {'Status': 'pending', 'code': 'stat',
                   'Description': 'First attempt at posting a review to Xena.  Hold on to something.\n',
                   'Client': 'sallan-xena-sample-depot',
                   'Jobs1': 'job000020', 'User': 'sallan', 'Date': '2015/03/18 17:59:07',
                   'Files0': '//depot/Jam/MAIN/src/README', 'Type': 'public', 'Change': '813',
                   'Jobs0': 'job000019'}

    def get_change_list(self, change_number):
        return self.change_list

    def test_find_bugs(self):
        p4 = p2.P4(user='sallan', port='xena:1492', client='sallan-xena-sample-depot')
        p4.get_change = self.get_change_list
        found = p4.get_jobs('813')
        expected = ['job000019', 'job000020']
        self.assertEqual(expected, found)


if __name__ == '__main__':
    main()
