#!/usr/bin/python

from unittest import TestCase
from unittest import main

import p2 as post


class TestArgParser(TestCase):
    def test_arguments_only(self):
        # With no actions or args, nothing happens
        test_args = ['post']
        post.RBArgParser(test_args)

        # Create without CL is okay
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('create', arg_parser.action)

        # Any other action without CL raises exception
        test_args = ['post', 'edit']
        with self.assertRaises(post.RBError):
            post.RBArgParser(test_args)

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
        with self.assertRaises(post.RBError):
            post.RBArgParser(test_args)
        test_args = ['post', '999', 'create', '123']
        with self.assertRaises(post.RBError):
            post.RBArgParser(test_args)

    def test_options_only(self):
        # NOTE: Need to pass an action and change list to avoid exception.

        # Options that get passed straight to rbt
        test_args = ['post', 'create', '--debug', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-d', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--debug', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--version', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--version', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-v', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--version', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '--server', 'http://rb', '999']
        arg_parser = post.RBArgParser(test_args)
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
        self.assertEqual(['--rid', '12345', '999'], arg_parser.rbt_args[2:])

        test_args = ['post', 'create', '-r', '12345', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual('12345', arg_parser.rid)
        self.assertEqual(['--rid', '12345', '999'], arg_parser.rbt_args[2:])

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

        test_args = ['post', 'create', '--force', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.force)

        # If the --shelve option is used with publish, we need to intercept
        # publish so we can add the shelve comment first. Otherwise let it go.
        test_args = ['post', 'create', '--publish', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--publish', '999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '-p', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['--publish', '999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '--publish', '999', '--shelve']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '999', '--shelve']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['999'], arg_parser.rbt_args[2:])
        self.assertFalse(arg_parser.publish)

    def Xtest_create_ui(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertIsNone(arg_parser.change_number)

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
        with self.assertRaises(post.RBError):
            post.RBArgParser(test_args)

    def Xtest_edit_ui(self):
        test_args = ['post', 'edit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(arg_parser.rbt_args[2:], ['999'])

        test_args = ['post', '-d', 'edit', '999', '--publish']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertTrue(arg_parser.publish)
        self.assertEqual(arg_parser.rbt_args[2:], ['--debug', '--publish', '999'])

        test_args = ['post', '-d', 'edit', '--shelve', '999', '-p']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertTrue(arg_parser.publish)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args[2:], ['--debug', '999'])

    def Xtest_submit_ui(self):
        test_args = ['post', 'submit']
        with self.assertRaises(post.RBError):
            post.RBArgParser(test_args)

        test_args = ['post', 'submit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)

        test_args = ['post', '-f', 'submit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertTrue(arg_parser.force)

        test_args = ['post', '-f', 'submit', '999', '-e']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(arg_parser.action, 'submit')
        self.assertEqual('999', arg_parser.change_number)
        self.assertTrue(arg_parser.force)
        self.assertTrue(arg_parser.edit_changelist)

    def Xtest_diff_ui(self):
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
        p4 = post.P4(user='sallan', port='xena:1492', client='sallan-xena-sample-depot')
        p4.get_change = self.get_change_list
        found = p4.get_jobs('813')
        expected = ['job000019', 'job000020']
        self.assertEqual(expected, found)


if __name__ == '__main__':
    main()