#!/usr/bin/env python

from unittest import TestCase
from unittest import main

import post


class TestArgParser(TestCase):
    def test_arguments_only(self):
        # With no actions or args, nothing happens
        test_args = ['post']
        post.RBArgParser(test_args)

        # Create without CL is okay
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)
        self.assertEqual(None, arg_parser.change_number)

        # Create review from submitted change(s)
        depot_paths = [
            '//depot/foo/...@10,@20',
            '//depot/foo/bar.c#1,#4'
            '//depot/foo/bar.c@123'
        ]
        for depot_path in depot_paths:
            test_args = ['post', 'create', depot_path]
            arg_parser = post.RBArgParser(test_args)
            self.assertEqual('create', arg_parser.action)
            self.assertEqual(None, arg_parser.change_number)
            self.assertEqual(depot_path, arg_parser.depot_path)

        # Action and CL can be in any order
        test_args = ['post', 'create', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)
        self.assertEqual('999', arg_parser.change_number)

        test_args = ['post', '999', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)
        self.assertEqual('999', arg_parser.change_number)

        # What if we get multiple change lists or actions?
        test_args = ['post', 'edit', '999', 'create']
        self.assertRaises(post.RBError, post.RBArgParser, test_args)
        test_args = ['post', '999', 'create', '123']
        self.assertRaises(post.RBError, post.RBArgParser, test_args)

    def test_options_only(self):
        # NOTE: Need to pass an action and change list to avoid exception.

        test_args = ['post', 'create', '--debug']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.debug)
        self.assertEqual(['--debug'], arg_parser.rbt_args[2:])

        # Options that get passed straight to rbt
        test_args = ['post', 'create', '--debug', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.debug)
        self.assertEqual(['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-d', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.debug)
        self.assertEqual(['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', '--version']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.version)

        test_args = ['post', '-v']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.version)

        test_args = ['post', 'create', '--server', 'http://rb', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('http://rb', arg_parser.server_url)
        self.assertEqual(['--server', 'http://rb', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--target-people', 'me, you, him', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--target-people', 'me, you, him', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--target-groups', 'us, them', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--target-groups', 'us, them', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--testing-done', 'no testing needed', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--testing-done', 'no testing needed', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--testing-done-file', '/dev/null', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--testing-done-file', '/dev/null', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--rid', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual(['--review-request-id', '12345', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-r', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual(['--review-request-id', '12345', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'edit', '--update-diff', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--update-diff', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'edit', '--change-only', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--change-only', '999'], arg_parser.rbt_args[2:])

        # Options we need to intercept
        test_args = ['post', 'create', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.shelve)

        test_args = ['post', 'edit', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.shelve)

        test_args = ['post', 'create', '--force', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.force)

        # If the --shelve option is used with publish, we need to intercept
        # publish so we can add the shelve comment first. Otherwise let it go.
        test_args = ['post', 'create', '--publish', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '-p', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '--publish', '999', '--shelve']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '999', '--shelve']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertFalse(arg_parser.publish)

        test_args = ['post', 'create', '999', '--branch', 'v1.0']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--branch', 'v1.0', '999'], arg_parser.rbt_args[2:])

        # Test use of depot path instead of CL
        depot_paths = [
            '//depot/foo/...@10,@20',
            '//depot/foo/bar.c#1,#4',
            '//depot/foo/bar.c@123',
            '//depot/foo/bar.c#7',
        ]
        for depot_path in depot_paths:
            test_args = ['post', 'create', depot_path, '--branch', 'v1.0']
            arg_parser = post.RBArgParser(test_args)
            self.assertEqual(arg_parser.depot_path, depot_path)
            self.assertEqual(['--branch', 'v1.0', depot_path], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '999', '--description', 'Best change ever!']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--description', 'Best change ever!', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '999', '--summary', 'Best change ever!']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--summary', 'Best change ever!', '999'], arg_parser.rbt_args[2:])

    def test_create_ui(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual(None, arg_parser.change_number)

        test_args = ['post', 'create', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertEqual(arg_parser.rbt_args[2:], ['999'])

        test_args = ['post', 'create', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], ['999'])

        test_args = ['post', 'create', '--debug', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], ['--debug', '999'])

        test_args = ['post', 'create', '--shelve', '999', '--debug']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], ['--debug', '999'])

        test_args = ['post', 'create', '--username', 'me', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertEqual(arg_parser.rbt_args[2:], ['--username', 'me', '999'])

        test_args = ['post', 'create', '--shelve', '999', '--debug', '-p']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertTrue(arg_parser.publish)
        self.assertEqual(arg_parser.rbt_args[2:], ['--debug', '999'])

        test_args = ['create', '999', '--server', 'http://rb', '999', '--debug', '999']
        self.assertRaises(post.RBError, post.RBArgParser, test_args)

    def test_edit_ui(self):
        test_args = ['post', 'edit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(arg_parser.rbt_args[2:], ['999'])

        test_args = ['post', '-d', 'edit', '999', '--publish']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertTrue(arg_parser.publish)
        self.assertEqual(['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', '-d', 'edit', '--shelve', '999', '-p']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertTrue(arg_parser.publish)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'edit', '--summary', 'Editing with a range', '-r' '12345']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(['--review-request-id', '12345', '--summary', 'Editing with a range'],
                         arg_parser.rbt_args[2:])

    def test_submit_ui(self):
        test_args = ['post', 'submit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertEqual([], arg_parser.rbt_args[2:])

        test_args = ['post', 'submit', '999', '-d']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertEqual(['--debug'], arg_parser.rbt_args[2:])

        test_args = ['post', '-f', 'submit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertTrue(arg_parser.force)
        self.assertEqual([], arg_parser.rbt_args[2:])

        test_args = ['post', '-f', 'submit', '999', '-e']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertTrue(arg_parser.force)
        self.assertTrue(arg_parser.edit_changelist)
        self.assertEqual([], arg_parser.rbt_args[2:])

        test_args = ['post', 'submit', '--rid', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual([], arg_parser.rbt_args[2:])

    def test_diff_ui(self):
        test_args = ['post', 'diff', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'diff')
        self.assertEqual('999', arg_parser.change_number)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])


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
        p4 = post.P4(user='sallan', port='localhost:1492', client='sallan-rbscript-test-depot')
        p4.get_change = self.get_change_list
        found = p4.get_jobs('813')
        expected = ['job000019', 'job000020']
        self.assertEqual(expected, found)


class TestConfigFile(TestCase):
    RC_FILE = 'reviewboardrc'

    def test_url_provided_on_command_line(self):
        test_args = ['post', 'create', '--server', 'http://rb']
        arg_parser = post.RBArgParser(test_args)
        url = post.get_url(arg_parser, self.RC_FILE)
        self.assertEqual("http://rb", url)

    def test_url_not_provided_on_command_line(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        url = post.get_url(arg_parser, self.RC_FILE)
        self.assertEqual("http://localhost", url)


class TestRidAccessor(TestCase):
    def no_rbt_api(self):
        pass

    def no_rid_from_cl(self):
        return None

    def testNoRidPassed(self):
        args = ['post', 'create', '999']
        arg_parser = post.RBArgParser(args)
        post.F5Review._get_rbt_api = self.no_rbt_api
        post.F5Review.get_review_id_from_changenum = self.no_rid_from_cl
        f5_review = post.F5Review("http://localhost", arg_parser)
        self.assertEqual(None, f5_review.rid)

    def testRidPassed(self):
        args = ['post', 'create', '--rid', '15', '999']
        post.F5Review._get_rbt_api = self.no_rbt_api
        post.F5Review.get_review_id_from_changenum = self.no_rid_from_cl
        arg_parser = post.RBArgParser(args)
        f5_review = post.F5Review("http://localhost", arg_parser)
        self.assertEqual("15", f5_review.rid)

        args = ['post', 'create', '-r', '16', '999']
        post.F5Review._get_rbt_api = self.no_rbt_api
        post.F5Review.get_review_id_from_changenum = self.no_rid_from_cl
        arg_parser = post.RBArgParser(args)
        f5_review = post.F5Review("http://localhost", arg_parser)
        self.assertEqual("16", f5_review.rid)


class TestUseOfDepotPaths(TestCase):
    def no_rbt_api(self):
        pass

    def no_rid_from_cl(self):
        return None

    def testNoRidPassed(self):
        depot_path = "//depot/foo/...@100,200"
        args = ['post', 'create', depot_path]
        arg_parser = post.RBArgParser(args)
        post.F5Review._get_rbt_api = self.no_rbt_api
        f5_review = post.F5Review("http://localhost", arg_parser)
        self.assertEqual(f5_review.depot_path, depot_path)


if __name__ == '__main__':
    main()
