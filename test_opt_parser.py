from unittest import TestCase

import p2


class TestOpt_parser(TestCase):
    def test_opt_parser(self):
        test_args = ['edit', '--debug', '999']
        action, args = p2.opt_parser(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--debug', '999'])

        test_args = ['edit', '999', '--debug']
        action, args = p2.opt_parser(test_args)
        self.assertEqual("edit", action)
        self.assertEqual(args, ['rbt', 'edit', '--debug', '999'])

        test_args = ['create', '999', '--server', 'http://rb', '999', '--debug', '999']
        action, args = p2.opt_parser(test_args)
        self.assertEqual("create", action)
        self.assertEqual(args, ['rbt', 'create', '--server', 'http://rb', '--debug', '999'])
