#!/usr/bin/python
import sys
import optparse

from rbtools.commands import post
from rbtools.commands import diff


ACTIONS = ['create', 'edit', 'submit', 'diff']


def opt_parser(args):
    myargs = args[:]
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug', dest='debug', action='store_true')
    parser.add_option('--shelve', dest='shelve', action='store_true')
    parser.add_option('--p4-port', dest='p4port')
    parser.add_option('--p4-client', dest='p4client')
    parser.add_option('--server', dest='server')

    opts, args = parser.parse_args(args)
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

    return action, ['rbt', action] + myargs + args


if __name__ == '__main__':
    action, args = opt_parser(sys.argv[1:])
    if action == 'diff':
        d = diff.Diff()
        d.run_from_argv(args)
    elif action == 'edit':
        p = post.Post()
        p.run_from_argv(args)

