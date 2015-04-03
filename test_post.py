#!/usr/bin/python

from unittest import TestCase
from unittest import main

import p2 as post


class TestArgParser(TestCase):
    def test_arguments_only(self):
        # No args raises exception
        test_args = ['post']
        with self.assertRaises(post.RBError):
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
        # NOTE: Need to pass an action and change listto avoid exception.

        # Options that get passed straight to rbt
        test_args = ['post', 'create', '--debug', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '--debug', '999'], arg_parser.rbt_args)

        test_args = ['post', 'create', '-d', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '-d', '999'], arg_parser.rbt_args)

        test_args = ['post', 'create', '--server', 'http://rb', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '--server', 'http://rb', '999'], arg_parser.rbt_args)

        test_args = ['post', 'create', '--target-people', 'me, you, them', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '--target-people', 'me, you, them', '999'], arg_parser.rbt_args)

        # Options we need to intercept
        test_args = ['post', 'create', '--publish', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '999'], arg_parser.rbt_args)
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '-p', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '999'], arg_parser.rbt_args)
        self.assertTrue(arg_parser.publish)

        test_args = ['post', 'create', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '999'], arg_parser.rbt_args)
        self.assertTrue(arg_parser.shelve)

        test_args = ['post', 'create', '--force', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual(['rbt', '999'], arg_parser.rbt_args)
        self.assertTrue(arg_parser.force)


    def Xtest_create_ui(self):
        test_args = ['post', 'create']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertIsNone(arg_parser.change_number)

        test_args = ['post', 'create', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertEqual(arg_parser.rbt_args, ['rbt', '999'])

        test_args = ['post', 'create', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args, ['rbt', '999'])

        test_args = ['post', 'create', '--debug', '--shelve', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args, ['rbt', '--debug', '999'])

        test_args = ['post', 'create', '--shelve', '999', '--debug']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("create", arg_parser.action)
        self.assertEqual("999", arg_parser.change_number)
        self.assertTrue(arg_parser.shelve)
        self.assertEqual(arg_parser.rbt_args, ['rbt', '--debug', '999'])

        '''
        test_args = ['post', 'edit', '999']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(arg_parser.rbt_args, ['rbt', '999'])

        test_args = ['post', 'edit', '999', '--debug']
        arg_parser = post.RBArgParser(test_args)
        self.assertEqual("edit", arg_parser.action)
        self.assertEqual(arg_parser.rbt_args, ['rbt', '--debug', '999'])
        '''

        '''
        test_args = ['create', '999', '--server', 'http://rb', '999', '--debug', '999']
        action, args = post.parse_options(test_args)
        self.assertEqual("create", action)
        self.assertEqual(args, ['rbt', 'create', '--server', 'http://rb', '--debug', '999'])

        test_args = ['edit', '999', '--publish']
        action, args = post.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--publish', '999'])
        '''

    def Xtest_f5_options(self):
        test_args = ['edit', '999', '--shelve']
        # action, f5_args, args = post.parse_options(test_args)
        action, args = post.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '999'])
        # TODO: Enable this assert
        # self.asserTrue(f5_args['shelve'])

        test_args = ['edit', '--shelve', '999', '--server', 'http://rb', '999', '--debug', '999']
        action, args = post.parse_options(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--server', 'http://rb', '--debug', '999'])

        test_args = ['submit', '--force', '999', '--server', 'http://rb']
        action, args = post.parse_options(test_args)
        self.assertEqual("submit", action)
        self.assertEqual(args, ['rbt', 'submit', '--server', 'http://rb', '999'])

        test_args = ['submit', '--force', '999', '--edit-changelist', '--server', 'http://rb']
        action, args = post.parse_options(test_args)
        self.assertEqual("submit", action)
        self.assertEqual(args, ['rbt', 'submit', '--server', 'http://rb', '999'])

        test_args = ['submit', '-f', '999']
        action, args = post.parse_options(test_args)
        self.assertEqual("submit", action)
        self.assertEqual(args, ['rbt', 'submit', '999'])


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
