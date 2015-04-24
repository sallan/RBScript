#!/usr/bin/env python
#
# An interactive test driver for p2.py
import os
from subprocess import check_call, CalledProcessError

from p2 import P4


p4 = P4()


def append_line(filename, line):
    with open(filename, "a") as f:
        f.write(line + "\n")


def p4_open(file):
    p4.run("edit " + file)


def pause():
    response = raw_input("Continue? ('q' to quit, any other key to continue): ")
    if response.lower() == 'q':
        raise SystemExit()


def ask_for_cl():
    cl = raw_input("Please enter change list number: ")
    return int(cl)


def ask_for_rid():
    rid = raw_input("Please enter RB ID number: ")
    return int(rid)


def announce(str):
    print "Tester==> %s" % str

# TODO: Maybe there's a better way to use different files?
file1 = "readme.txt"
file2 = "relnotes.txt"


# Start of as a brand new user with a clean slate, which
# means you don't yet have login cookies
announce("When we create this review, we should get prompted for login.")
rb_cookies_file = os.path.join(os.path.expanduser(os.environ['HOME']), ".rbtools-cookies")
rb_cookies_file_backup = rb_cookies_file + ".backup"
if os.path.isfile(rb_cookies_file):
    os.rename(rb_cookies_file, rb_cookies_file_backup)
p4_open(file1)
append_line(file1, "When you post this, you should get prompted for login")
check_call("p2.py create --target-people sallan", shell=True)
announce("Review posted - go publish it.")
pause()

announce("Going to shelve and publish this change now.")
append_line(file1, "Okay, add a change and shelve it.")
cl1 = ask_for_cl()
check_call("p2.py edit --shelve -p %s" % cl1, shell=True)
pause()

announce("Creating a second review with a branch.")
p4_open(file2)
append_line(file2, "Review with a branch")
check_call("p2.py create --target-people sallan --branch 'my branch' -p", shell=True)
pause()
announce("Now adding 2 jobs")
cl2 = ask_for_cl()
jobs = ['job000010', 'job000011']
for job in jobs:
    check_call("p4 fix -c %s %s" % (cl2, job), shell=True)
check_call("p2.py edit -p %s" % cl2, shell=True)
pause()
announce("Submit the second review first so first review will get a new CL number")
check_call("p2.py submit --force %s" % cl2, shell=True)
pause()

announce("Attempting to submit first review without a ship it.")
try:
    check_call("p2.py submit %s" % cl1, shell=True)
except CalledProcessError as e:
    pass
announce("Please go give me a ship it.")
pause()
announce("Attempting to submit with a ship it.")
check_call("p2.py submit %s" % cl1, shell=True)
announce("See if the CL number changed for the first review.")

announce("Show that we can block a review with only a reviewbot ship it.")
p4_open(file1)
append_line(file1, "Review that only Review Bot likes.")
check_call("p2.py create --target-people sallan -p", shell=True)
announce("Now go and have Review Bot give it a ship it.")
pause()
announce("Attempting to submit review with only a Review Bot ship it.")
cl = ask_for_cl()
rid = ask_for_rid()
try:
    check_call("p2.py submit %s" % cl, shell=True)
except CalledProcessError as e:
    pass
announce("Now go and give it a proper ship it.")
pause()
announce("Attempting to submit with a ship it.")
check_call("p2.py submit %s" % cl, shell=True)
pause()

announce("Now we'll try editing a review with a new CL.")
announce("Please re-open review %s" % rid)
p4_open(file1)
append_line(file1, "This file needs more work. How did it ever get approved?")
check_call("p4 change", shell=True)
announce("First try editing with rid - we should get a helpful message.")
cl = ask_for_cl()
try:
    check_call("p2.py edit %s" % cl, shell=True)
except CalledProcessError as e:
    pass
pause()
announce("Now we'll try the rid option.")
check_call("p2.py edit -r %s %s -p" % (rid, cl), shell=True)
announce("Check the diff for the updated review.")
pause()

announce("When we submit without rid, we should get blocked and CL should remain open")
try:
    check_call("p2.py submit %s" % cl, shell=True)
except CalledProcessError as e:
    pass
pause()

announce("Now submit.")
check_call("p2.py submit -r %s %s" % (rid, cl), shell=True)


# Before leaving, restore original rbtools cookie file
if os.path.isfile(rb_cookies_file_backup):
    os.rename(rb_cookies_file_backup, rb_cookies_file)
