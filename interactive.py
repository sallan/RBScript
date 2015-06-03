#!/usr/bin/env python
#
# An interactive test driver for post
import os
from subprocess import check_call, CalledProcessError

from post import P4

p4 = P4()

os.environ['PATH'] = os.getcwd() + ':' + os.environ['PATH']
def append_line(filename, line):
    with open(filename, "a") as f:
        f.write(line + "\n")


def p4_open(file):
    p4.run("edit " + file)


def pause(msg=None):
    if msg is not None:
        print msg
    response = raw_input("Continue? ('q' to quit, any other key to continue): ")
    if response.lower() == 'q':
        raise SystemExit()


def ask_for_cl():
    cl = raw_input("Please enter change list number: ")
    return int(cl)


def ask_for_rid():
    rid = raw_input("Please enter RB ID number: ")
    return str(int(rid))


def announce(str):
    print "Tester==> %s" % str

# TODO: Maybe there's a better way to use different files?
file1 = "readme.txt"
file2 = "relnotes.txt"

rb_cookies_file = os.path.join(os.path.expanduser(os.environ['HOME']), ".rbtools-cookies")
rb_cookies_file_backup = rb_cookies_file + ".backup"

# Start of as a brand new user with a clean slate, which
# means you don't yet have login cookies and should get
# prompted for a login.
announce("When we create this review, we should get prompted for login.")
if os.path.isfile(rb_cookies_file):
    os.rename(rb_cookies_file, rb_cookies_file_backup)
p4_open(file1)
append_line(file1, "When you post this, you should get prompted for login")
check_call("post create --target-people sallan", shell=True)
pause("Review posted - go publish it.")

# Demonstrate editing and shelving
announce("Going to shelve and publish this change now.")
append_line(file1, "Okay, add a change and shelve it.")
cl1 = ask_for_cl()
check_call("post edit --shelve -p %s" % cl1, shell=True)
pause()

# Demonstrate adding a branch label and possibly jobs
pause("Creating a second review with a branch.  Add jobs to the change of you want.")

p4_open(file2)
append_line(file2, "Review with a branch and maybe some jobs")
check_call("post create --target-people sallan --branch 'my branch' -p", shell=True)
pause()
announce("Submit the second review first so first review will get a new CL number")
cl2 = ask_for_cl()
check_call("post submit --force %s" % cl2, shell=True)
pause()

# Demonstrate submitting without a ship it and the with.
# You can also see that RB eventually updates the CL with
# the submitted number.
announce("Attempting to submit first review without a ship it.")
try:
    check_call("post submit %s" % cl1, shell=True)
except CalledProcessError as e:
    pass
pause("Please go give me a ship it.")
announce("Attempting to submit with a ship it.")
check_call("post submit %s" % cl1, shell=True)

# Demonstrate blocking a review with only a reviewbot ship it
pause("Show that we can block a review with only a reviewbot ship it.")
p4_open(file1)
append_line(file1, "Review that only Review Bot likes.")
check_call("post create --target-people sallan -p", shell=True)
pause("Now go and have Review Bot give it a ship it.")
announce("Attempting to submit review with only a Review Bot ship it.")
cl = ask_for_cl()
announce("I also need the rid for the next test.")
rid = ask_for_rid()
try:
    check_call("post submit %s" % cl, shell=True)
except CalledProcessError:
    pass
pause("Now go and give it a proper ship it.")
announce("Attempting to submit with a ship it.")
check_call("post submit %s" % cl, shell=True)
pause()

# Demonstrate editing an existing review with a different CL
announce("Now we'll try editing a review with a new CL.")
pause("Please re-open review %s" % rid)
p4_open(file1)
append_line(file1, "This file needs more work. How did it ever get approved?")
check_call("p4 change", shell=True)
announce("First try editing without rid - we should get a helpful message.")
cl = ask_for_cl()
try:
    check_call("post edit %s" % cl, shell=True)
except CalledProcessError:
    pass
pause()
announce("Now we'll try the rid option.")
check_call("post edit -r %s %s -p" % (rid, cl), shell=True)
pause("Check the diff for the updated review.")

announce("When we submit without rid, we should get blocked and CL should remain open")
try:
    check_call("post submit %s" % cl, shell=True)
except CalledProcessError:
    pass
pause()

announce("Now submit.")
check_call("post submit -r %s %s" % (rid, cl), shell=True)
pause("NOTE: This worked without -f because the review already had a ship it.")

# Demonstrate creating reviews with submitted change lists
pause("Now creating a review with submitted change lists")
path = "//depot/Jam/MAIN/src/...@139,@140"
description = "Review from submitted CLs"
command = 'post create  %s --summary "%s" --description "%s" --target-people sallan' \
          % (path, description, description)
check_call(command, shell=True)
pause("Check the diffs")
path = "//depot/Jam/MAIN/src/...@139,@141"
announce("Now we'll update it. First try without the rid")
command = 'post edit %s' % path
try:
    check_call(command, shell=True)
except CalledProcessError:
    pass
rid = ask_for_rid()
command += " --publish --rid " + str(rid)
check_call(command, shell=True)
pause("Check for the new diff")
pause("Now let's try to submit it - first forgetting the --rid option")
try:
    check_call("post submit " + rid, shell=True)
except CalledProcessError:
    pass
announce("Now do it right")
check_call("post submit -r %s -f" % rid, shell=True)

pause("Now time to show some diffs")
p4_open(file2)
append_line(file2, "This is the first diff I want to see")
check_call("post diff", shell=True)
pause("Diff ok?")
pause("Next create a change")
check_call("p4 change", shell=True)
announce("Adding another diff")
append_line(file2, "This is the second diff I want to see")
cl = ask_for_cl()
check_call("post diff %s" % cl, shell=True)


# Before leaving, restore original rbtools cookie file
if os.path.isfile(rb_cookies_file_backup):
    os.rename(rb_cookies_file_backup, rb_cookies_file)
