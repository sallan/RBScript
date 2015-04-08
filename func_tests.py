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
        self.workdir = self.p4.run_info()[0]['clientRoot']
        self.rbapi_root = RBClient("http://localhost").get_root()
        self.readme = os.path.join(self.workdir, "readme.txt")
        self.relnotes = os.path.join(self.workdir, "relnotes.txt")

    def tearDown(self):
        self.p4.disconnect()

    def test_simple_create_and_update(self):
        self.p4.run_edit(self.readme)

        # Create first review request
        os.system("echo 'New change' >> %s" % self.readme)
        change = self.p4.fetch_change()
        change['Description'] = "First test case\n"
        change_output = self.p4.save_change(change)
        cl1 = int(change_output[0].split()[1])
        self.p4.run('fix', '-c', cl1, 'job000010')
        os.system("./p2.py create --server http://localhost --target-people sallan %d -p --branch mybranch" % cl1)
        rr1 = self.rbapi_root.get_review_request(review_request_id=1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertEqual('First test case', rr1.summary)
        self.assertEqual(cl1, rr1.changenum)
        self.assertEqual(['job000010'], rr1.bugs_closed)
        self.assertEqual('pending', rr1.status)
        self.assertTrue(rr1.public)

        # Edit first rr
        os.system("echo 'Better change' >> %s" % self.readme)
        os.system("./p2.py edit --server http://localhost %s" % cl1)
        draft = rr1.get_draft()
        self.assertFalse(draft.public)
        draft.update(public=True)

        # Create a second review request
        self.p4.run_edit(self.relnotes)
        os.system("echo 'New release note.' >> %s" % self.relnotes)
        change = self.p4.fetch_change()
        change['Description'] = "Second test case\n"
        change_output = self.p4.save_change(change)
        cl2 = int(change_output[0].split()[1])
        os.system("./p2.py create --server http://localhost --target-people sallan %d -p --branch mybranch" % cl2)
        rr2 = self.rbapi_root.get_review_request(review_request_id=2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertEqual('Second test case', rr2.summary)
        #self.assertEqual('sallan', rr1.target_people)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual('pending', rr2.status)
        self.assertTrue(rr2.public)

        # Submit second request
        os.system("./p2.py submit --server http://localhost %s -f" % cl2)
        rr2 = self.rbapi_root.get_review_request(review_request_id=2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertTrue(rr2.public)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual('submitted', rr2.status)

        # Submit first request and verify tha change number was updated
        os.system("./p2.py submit --server http://localhost %s -f" % cl1)
        rr1 = self.rbapi_root.get_review_request(review_request_id=2)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertTrue(rr1.public)

        # Since cl2 was submitted, this cl will have to be renumbered to be cl2 + 1
        self.assertEqual(cl2 + 1, rr1.changenum)
        self.assertEqual('submitted', rr1.status)

        # os.system("echo 'This should not publish because I have not implemented that yet' >> %s" % self.readme)
        # os.system("./p2.py edit --debug --publish --server http://localhost %s" % change_number)
        # draft = rr.get_draft()
        # self.assertFalse(draft.public)
        # draft.delete()

        #os.system("./p2.py edit --server http://localhost %s -p" % change_number)
        #self.assertEqual(0, rr.ship_it_count)


if __name__ == '__main__':
    main()
