#!/usr/bin/python
import sys
import optparse

from rbtools.commands import post
from rbtools.commands import diff


ACTIONS = ['create', 'edit', 'submit', 'diff']


def get_option_parser():
    """Options parser and usage."""

    description = """
Create, update and submit review requests.

This script is a wrapper to the rbt commands that come with RBTools. It
can only be used with perforce and provides some additional functionality
related to perforce.  The work flow is create/edit/submit. Alternatively,
the diff command will print a Review Board compatible diff of a change list
to STDOUT without creating or modify a review.

The options for each command are described below.

"""

    parser = optparse.OptionParser(
        usage="%prog [OPTIONS] create|edit|submit|diff [changenum]",
        description=description
    )
    parser.add_option("-v", "--version",
                      default=False, dest="version", action="store_true",
                      help="Display version and exit.")
    parser.add_option("-d", "--debug",
                      dest="debug", action="store_true", default=False,
                      help="Display debug output.")
    parser.add_option("--server",
                      dest="server", metavar="<server_name>",
                      help="Use specified server. Default is the REVIEWBOARD_URL entry in .reviewboardrc file.")

    submit_group = optparse.OptionGroup(parser, "Submit Options")
    submit_group.add_option("-f", "--force",
                            dest="force", action="store_true", default=False,
                            help="Submit even if the review doesn't meet all requirements.")
    submit_group.add_option("-e", "--edit-changelist",
                            dest="edit", action="store_true", default=False,
                            help="Edit the change list before submitting.")

    edit_group = optparse.OptionGroup(parser, "Create and Edit Options")
    edit_group.add_option("-p", "--publish",
                          dest="publish", action="store_true", default=False,
                          help="Publish the review.")
    edit_group.add_option("-n", "--output-diff",
                          dest="output_diff_only", action="store_true", default=False,
                          help="Output diff to console and exit. Do not post.")
    edit_group.add_option("--target-groups",
                          dest="target_groups", metavar="<group [,groups]>",
                          help="Assign or replace ReviewBoard groups for this review.")
    edit_group.add_option("--target-people",
                          dest="target_people", metavar="<user [,users]>",
                          help="Assign or replace reviewers for this review.")
    edit_group.add_option("--branch",
                          dest="branch", metavar="<branch [,branch]>",
                          help="Assign or replace branches for this review. Accepts any string.")

    edit_group.add_option("--shelve",
                          dest="shelve", action="store_true", default=False,
                          help="Create or update p4 shelve for the files in the review.")
    edit_group.add_option("--update-diff",
                          dest="diff_only", action="store_true", default=False,
                          help="Uploads a new diff, but does not update information from change list.")
    edit_group.add_option("--change-only",
                          dest="change_only", action="store_true", default=False,
                          help="Updates info from change list, but does not upload diff.")
    edit_group.add_option("--testing-done",
                          dest="testing_done", metavar="<string>",
                          help="Description of testing done.")
    edit_group.add_option("--testing-done-file",
                          dest="testing_file", metavar="<filename>",
                          help="Text file containing description of testing done.")
    edit_group.add_option("-r", "--rid",
                          dest="rid", metavar="<ID>",
                          help="Upload changes to specific review by ID. Use this if your change list is different from the one associated with ID.")

    edit_group.add_option("--username",
                          dest="username", metavar="<user>",
                          help="Switch to this Review Board username. Useful if different from p4 username (e.g. mergeit). " +
                               "The new login credentials will remain in effect until you use --username again.")

    parser.add_option_group(edit_group)
    parser.add_option_group(submit_group)
    return parser


def parse_options(args):
    myargs = args[:]
    parser = get_option_parser()
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
    action, args = parse_options(sys.argv[1:])
    if action == 'diff':
        d = diff.Diff()
        d.run_from_argv(args)
    elif action == 'edit':
        p = post.Post()
        p.run_from_argv(args)

