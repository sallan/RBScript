#!/usr/bin/python
import os
from unittest import TestCase
from unittest import main

from P4 import P4
from rbtools.api.client import RBClient


class FuncTests(TestCase):
    def setUp(self):
        os.environ['P4CONFIG'] = 'p4.config'
        self.p4 = P4()
        self.p4.port = "localhost:1492"
        self.p4.user = "sallan"
        self.p4.client = "sallan-rbscript-test-depot"
        self.p4.connect()
        os.chdir(self.p4.run_info()[0]['clientRoot'])
        self.rbapi_root = RBClient("http://localhost").get_root()


    def tearDown(self):
        self.p4.disconnect()

    def test_simple_create_and_update(self):
        self.p4.run_edit("readme.txt")
        os.system("echo 'New change' >> readme.txt")
        change = self.p4.fetch_change()
        change['Description'] = "First test case\n"
        change_output = self.p4.save_change(change)
        change_number = change_output[0].split()[1]
        os.system("./p2.py create --server http://localhost --target-people sallan -p %s" % change_number)

        rr = self.rbapi_root.get_review_requests()[0]
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertTrue(rr.public)

        os.system("echo 'Better change' >> readme.txt")
        os.system("./p2.py edit --server http://localhost %s" % change_number)
        draft = rr.get_draft()
        self.assertFalse(draft.public)
        draft.delete()

        os.system("./p2.py edit --server http://localhost %s -p" % change_number)
        self.assertEqual(0, rr.ship_it_count)


if __name__ == '__main__':
    main()
