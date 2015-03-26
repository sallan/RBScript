#!/usr/bin/python
from rbtools.commands import post
from rbtools.commands import diff
import sys

myargs = sys.argv[:]

myargs[0:1] = ['rbt']
print myargs

if myargs[1] == 'diff':
    d = diff.Diff()
    d.run_from_argv(myargs)

# p = post.Post()
# p.run_from_argv(myargs)
