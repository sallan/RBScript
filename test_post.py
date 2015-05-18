#!/usr/bin/env python

from unittest import TestCase
from unittest import main

import post

REPO = ["--repository-type", "perforce"]

class TestArgParsing(TestCase):
    def test_no_args(self):
        # With no actions or args, help displayed
        test_args = ['post']
        post.RBArgParser(test_args)

    def test_create_with_default_cl(self):
        # Create without CL is okay
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)
        self.assertEqual(None, arg_parser.change_number)

    def test_create_from_submitted_change_lists(self):
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

    def test_create_with_new_cl(self):
        # Action and CL can be in any order
        test_args = ['post', 'create', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)
        self.assertEqual('999', arg_parser.change_number)

        test_args = ['post', '999', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)
        self.assertEqual('999', arg_parser.change_number)

    def test_mutiple_actions(self):
        # What if we get multiple change lists or actions?
        test_args = ['post', 'edit', '999', 'create']
        self.assertRaises(post.RBError, post.RBArgParser, test_args)
    
    def test_multiple_change_lists(self):
        test_args = ['post', '999', 'create', '123']
        self.assertRaises(post.RBError, post.RBArgParser, test_args)

class TestAllOptions(TestCase):
    REPO = ['--repository-type', 'perforce']

    def test_no_options_should_set_repo_type(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO, arg_parser.rbt_args[2:])

    def test_debug(self):
        test_args = ['post', 'create', '--debug']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.debug)
        self.assertEqual(REPO + ['--debug'], arg_parser.rbt_args[2:])

        # Options that get passed straight to rbt
        test_args = ['post', 'create', '--debug', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.debug)
        self.assertEqual(REPO + ['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-d', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.debug)
        self.assertEqual(REPO + ['--debug', '999'], arg_parser.rbt_args[2:])

    def test_version(self):
        test_args = ['post', '--version']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.version)

        test_args = ['post', '-v']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.version)

    def test_server(self):
        test_args = ['post', 'create', '--server', 'http://rb', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('http://rb', arg_parser.server_url)
        self.assertEqual(REPO + ['--server', 'http://rb', '999'], arg_parser.rbt_args[2:])

    def test_target_people(self):
        test_args = ['post', 'create', '--target-people', 'me, you, him', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--target-people', 'me, you, him', '999'], arg_parser.rbt_args[2:])

    def test_target_groups(self):
        test_args = ['post', 'create', '--target-groups', 'us, them', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--target-groups', 'us, them', '999'], arg_parser.rbt_args[2:])

    def test_testing_done(self):
        test_args = ['post', 'create', '--testing-done', 'no testing needed', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--testing-done', 'no testing needed', '999'], arg_parser.rbt_args[2:])

    def test_testing_done_file(self):
        test_args = ['post', 'create', '--testing-done-file', '/dev/null', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--testing-done-file', '/dev/null', '999'], arg_parser.rbt_args[2:])

    def test_rid(self):
        test_args = ['post', 'create', '--rid', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual(REPO + ['--review-request-id', '12345', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-r', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual(REPO + ['--review-request-id', '12345', '999'], arg_parser.rbt_args[2:])

    def test_update_diff(self):
        test_args = ['post', 'edit', '--update-diff', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--update-diff', '999'], arg_parser.rbt_args[2:])

    def test_change_only(self):
        test_args = ['post', 'edit', '--change-only', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--change-only', '999'], arg_parser.rbt_args[2:])

    def test_shelve(self):
        # Options we need to intercept
        test_args = ['post', 'create', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'edit', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])

    def test_force(self):
        test_args = ['post', 'create', '--force', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.force)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--publish', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '-p', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

    def test_shelve_with_publish(self):
        # If the --shelve option is used with publish, we need to intercept
        # publish so we can add the shelve comment first. Otherwise let it go.
        test_args = ['post', 'create', '--publish', '999', '--shelve']
        arg_parser = post.RBArgParser(test_args)
        self.assertTrue(arg_parser.publish)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '999', '--shelve']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])
        self.assertFalse(arg_parser.publish)

    def test_branch(self):
        test_args = ['post', 'create', '999', '--branch', 'v1.0']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--branch', 'v1.0', '999'], arg_parser.rbt_args[2:])

    def test_depot_path(self):
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
            self.assertEqual(REPO + ['--branch', 'v1.0', depot_path], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '999', '--description', 'Best change ever!']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--description', 'Best change ever!', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '999', '--summary', 'Best change ever!']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(REPO + ['--summary', 'Best change ever!', '999'], arg_parser.rbt_args[2:])


class TestCreateUi(TestCase):
    REPO = ["--repository-type", "perforce"]

    def test_default_change_list(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual(None, arg_parser.change_number)

    def test_existing_change_list(self):
        test_args = ['post', 'create', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['999'])

    def test_shelving(self):
        test_args = ['post', 'create', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['999'])

    def test_debug(self):
        test_args = ['post', 'create', '--debug', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['--debug', '999'])

        test_args = ['post', 'create', '--shelve', '999', '--debug']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['--debug', '999'])

    def test_username(self):
        test_args = ['post', 'create', '--username', 'me', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['--username', 'me', '999'])

    def test_publish(self):
        test_args = ['post', 'create', '--shelve', '999', '--debug', '-p']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertTrue(arg_parser.publish)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['--debug', '999'])

    def test_server_option(self):
        test_args = ['create', '999', '--server', 'http://rb', '999', '--debug', '999']
        self.assertRaises(post.RBError, post.RBArgParser, test_args)

class TestEditUi(TestCase):
    REPO = ["--repository-type", "perforce"]

    def test_edit(self):
        test_args = ['post', 'edit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(arg_parser.rbt_args[2:], REPO + ['999'])

    def test_publish(self):
        test_args = ['post', '-d', 'edit', '999', '--publish']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertTrue(arg_parser.publish)
        self.assertEqual(REPO + ['--debug', '999'], arg_parser.rbt_args[2:])

    def test_publish_with_shelve(self):
        # If the --shelve option is used with publish, we need to intercept
        # publish so we can add the shelve comment first. Otherwise let it go.
        test_args = ['post', '-d', 'edit', '--shelve', '999', '-p']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertTrue(arg_parser.publish)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(REPO + ['--debug', '999'], arg_parser.rbt_args[2:])

    def test_rid_and_summary(self):
        test_args = ['post', 'edit', '--summary', 'Editing with a summary', '-r' '12345']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(REPO + ['--review-request-id', '12345', '--summary', 'Editing with a summary'],
                         arg_parser.rbt_args[2:])


class TestSubmitUi(TestCase):
    def test_submit(self):
        test_args = ['post', 'submit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertEqual(REPO, arg_parser.rbt_args[2:])

    def test_debug(self):
        test_args = ['post', 'submit', '999', '-d']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertEqual(REPO + ['--debug'], arg_parser.rbt_args[2:])

    def test_force(self):
        test_args = ['post', '-f', 'submit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertTrue(arg_parser.force)
        self.assertEqual(REPO, arg_parser.rbt_args[2:])

    def test_edit(self):
        test_args = ['post', '-f', 'submit', '999', '-e']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertTrue(arg_parser.force)
        self.assertTrue(arg_parser.edit_changelist)
        self.assertEqual(REPO, arg_parser.rbt_args[2:])


    def test_rid(self):
        test_args = ['post', 'submit', '--rid', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual(REPO, arg_parser.rbt_args[2:])


class TestDiffUi(TestCase):
    def test_diff(self):
        test_args = ['post', 'diff', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'diff')
        self.assertEqual('999', arg_parser.change_number)
        self.assertEqual(REPO + ['999'], arg_parser.rbt_args[2:])


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

    def test_no_config_file(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertRaises(post.RBError, post.get_url, arg_parser, "no_such_file")


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
