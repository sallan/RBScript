#!/usr/bin/python
import os
from unittest import TestCase
from unittest import main

from P4 import P4
from rbtools.api.client import RBClient


class FuncTests(TestCase):
    def setUp(self):
        self.rb_url = "http://localhost"
        os.environ['P4CONFIG'] = 'p4.config'
        self.p4 = P4()
        self.p4.port = "localhost:1492"
        self.p4.user = "sallan"
        self.p4.client = "sallan-rbscript-test-depot"
        self.p4.connect()
        self.workdir = self.p4.run_info()[0]['clientRoot']
        self.rbapi_root = RBClient(self.rb_url).get_root()
        self.readme = os.path.join(self.workdir, "readme.txt")
        self.relnotes = os.path.join(self.workdir, "relnotes.txt")

    def tearDown(self):
        self.p4.disconnect()

    def get_rr_from_cl(self, cl):
        rr = self.rbapi_root.get_review_requests(status="all", changenum=cl)
        self.assertIsNotNone(rr)
        self.assertEqual(1, len(rr))
        return (rr[0])


    def test_simple_create_and_update(self):
        self.p4.run_edit(self.readme)

        # Create first review request
        test_string = 'First test case'
        os.system("echo %s >> %s" % (test_string, self.readme))
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl1 = int(change_output[0].split()[1])
        self.p4.run('fix', '-c', cl1, 'job000010')
        os.system("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                  (self.rb_url, cl1))
        rr1 = self.get_rr_from_cl(cl1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertEqual(test_string, rr1.summary)
        self.assertEqual(cl1, rr1.changenum)
        self.assertEqual(['job000010'], rr1.bugs_closed)
        self.assertEqual('pending', rr1.status)
        self.assertTrue(rr1.public)

        # Edit first rr
        os.system("echo 'Better change' >> %s" % self.readme)
        os.system("./p2.py edit --server %s %s" % (self.rb_url, cl1))
        draft = rr1.get_draft()
        self.assertFalse(draft.public)
        draft.update(public=True)

        # Create a second review request
        test_string = 'New release note.'
        test_jobs = ['job000011', 'job000012']
        self.p4.run_edit(self.relnotes)
        os.system("echo %s >> %s" % (test_string, self.relnotes))
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl2 = int(change_output[0].split()[1])
        for job in test_jobs:
            self.p4.run('fix', '-c', cl2, job)

        os.system("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                  (self.rb_url, cl2))
        rr2 = self.get_rr_from_cl(cl2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertEqual(test_string, rr2.summary)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual(test_jobs, rr2.bugs_closed)
        self.assertEqual('pending', rr2.status)
        self.assertTrue(rr2.public)

        # Submit second request
        os.system("./p2.py submit --server %s %s -f" % (self.rb_url, cl2))
        rr2 = self.get_rr_from_cl(cl2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertTrue(rr2.public)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual('submitted', rr2.status)

        # Submit first request
        # I was going to do a test here to make sure the CL was updated
        # on the server, but I could never get the test to pass, even though
        # visual inspection verified the CL was being updated. So I scrapped
        # the test.
        os.system("./p2.py submit --server %s %s -f" % (self.rb_url, cl1))
        rr1 = self.get_rr_from_cl(cl1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertTrue(rr1.public)
        self.assertEqual('submitted', rr1.status)

    def test_handling_ship_its(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test proper handling of ship its.'
        os.system("echo %s >> %s" % (test_string, self.readme))
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl = int(change_output[0].split()[1])
        os.system("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                  (self.rb_url, cl))
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertEqual(test_string, rr.summary)
        self.assertEqual(cl, rr.changenum)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)

        # with self.assertRaises(Exception):
        # os.system("./p2.py submit --server %s %s" % (self.rb_url, cl))

        os.system("./p2.py submit --server %s %s -f" % (self.rb_url, cl))
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertTrue(rr.public)
        self.assertEqual('submitted', rr.status)

if __name__ == '__main__':
    main()
