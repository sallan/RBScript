#!/usr/bin/env python
#
# This is an interactive script to test the use case of
# of submitting a review under the mergeit account. Before
# this test can be run, you need to set up these accounts:
#
# - unix accounts for sallan, buffy and mergeit
# - RB accounts for sallan and buffy
#
# Then run this script as mergeit.  Two perforce workspaces
# will be created under whatever directory you run this from.
# ===================================================================
import subprocess
import os

from P4 import P4, P4Exception


RB_URL = 'http://localhost'
P4_PORT = 'localhost:1492'


def setup_ws(user, ws_name, dirname):
    """Create client 'name' in 'dir'"""
    if not os.path.isdir(dirname):
        os.mkdir(dirname)

    with open(os.path.join(dirname, 'p4.config'), 'w') as f:
        f.write("P4PORT=%s\n" % P4_PORT)
        f.write("P4CLIENT=%s\n" % ws_name)

        p4 = P4()
        p4.user = user
        p4.port = P4_PORT
        p4.client = ws_name
        p4.connect()
        try:
            p4.run_client("-f", "-d", ws_name)
        except P4Exception:
            # I don't care if the old client wasn't deleted.
            pass
        try:
            client = p4.fetch_client("-t", "sallan-rbscript-test-depot")
            client._root = dirname
            p4.save_client(client)
            p4.run_sync('-f')
            p4.disconnect()
        except P4Exception as ex:
            # we don't care about warnings, just errors
            if p4.errors:
                for err in p4.errors:
                    print err
                raise ex


def create_new_change(p4, description):
    change = p4.fetch_change()
    change['Description'] = description + "\n"
    change_output = p4.save_change(change)
    change_number = int(change_output[0].split()[1])
    return change_number


def create_review(user, ws, ws_name, filename):
    os.chdir(ws)
    p4 = P4()
    p4.user = 'mergeit'
    p4.port = P4_PORT
    p4.client = ws_name
    p4.connect()
    p4.run_edit(filename)
    test_string = "Create a review as %s" % user
    with open(filename, 'a') as f:
        f.write(test_string)
    cl = create_new_change(p4, test_string)
    # subprocess.check_call("rbt post --server %s --submit-as %s %s" % (RB_URL, user, cl), shell=True)
    subprocess.check_call("p2.py create --server %s --username %s %s" % (RB_URL, user, cl), shell=True)


if __name__ == "__main__":
    working_dir = os.getcwd()
    buffy_ws = os.path.join(working_dir, 'buffy_ws')
    sallan_ws = os.path.join(working_dir, 'sallan_ws')

    print "Removing .rbtools-cookies files"
    rbcookies_file = os.path.join(os.path.expanduser('~'), '.rbtools-cookies')
    if os.path.isfile(rbcookies_file):
        os.remove(rbcookies_file)

    print "Creating workspaces"
    setup_ws("buffy", 'buffy-as-mergeit', buffy_ws)
    setup_ws("sallan", 'sallan-as-mergeit', sallan_ws)

    print "Creating review as buffy"
    create_review("buffy", buffy_ws, 'buffy-as-mergeit', os.path.join(buffy_ws, 'readme.txt'))
    print "Ensuring that the cookies file is gone."
    assert not os.path.isfile(rbcookies_file)

    print "Creating review as sallan"
    create_review("sallan", sallan_ws, 'sallan-as-mergeit', os.path.join(sallan_ws, 'relnotes.txt'))
    print "Ensuring that the cookies file is gone."
    assert not os.path.isfile(rbcookies_file)

    print "See if buffy and sallan both have reviews"

