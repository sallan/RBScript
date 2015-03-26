#!/usr/bin/python
import sys
import optparse

from rbtools.commands import post
from rbtools.commands import diff


ACTIONS = ['create', 'edit', 'submit', 'diff']


def opt_parser(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug', dest='debug', action='store_true')
    parser.add_option('--shelve', dest='shelve', action='store_true')
    parser.add_option('--p4-port', dest='p4port')
    parser.add_option('--p4-client', dest='p4client')
    parser.add_option('--server', dest='server')
    return parser.parse_args(args)


if __name__ == '__main__':
    myargs = sys.argv[1:]
    opts, args = opt_parser(sys.argv[1:])

    # Remove all occurrences of the args from the original list so we
    # can build up a list that argparse likes
    for arg in args:
        myargs.remove(arg)

    # Now remove duplicates from args list
    args = list(set(args))

    # Look for one and only one action
    requested_actions = []
    for action in ACTIONS:
        if action in args:
            requested_actions.append(action)
            args.remove(action)

    if len(requested_actions) != 1:
        print "Please provide exactly one action: " + ' | '.join(ACTIONS)
        raise SystemExit(1)
    else:
        action = requested_actions[0]

    if action == 'diff':
        myargs = ['rbt', 'diff'] + myargs + args
        d = diff.Diff()
        d.run_from_argv(myargs)
    elif action == 'edit':
        myargs = ['rbt', 'edit'] + myargs + args
        p = post.Post()
        p.run_from_argv(myargs)

