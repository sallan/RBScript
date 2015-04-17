#!/usr/bin/python
#
# An interactive test driver for p2.py
import os
from subprocess import check_call, CalledProcessError
import sys
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

announce("Attempting to submit without a ship it.")
try:
    check_call("p2.py submit %s" % cl1, shell=True)
except CalledProcessError as e:
    pass
announce("Please go give me a ship it.")
pause()
announce("Attempting to submit with a ship it.")
check_call("p2.py submit %s" % cl1, shell=True)

# Before leaving, restore original rbtools cookie file
if os.path.isfile(rb_cookies_file_backup):
    os.rename(rb_cookies_file_backup, rb_cookies_file)
