#!/usr/bin/env python
import sys
import os
import postreview
#from rbtools.clients.perforce import PerforceClient

import tempfile

def run_cmd(cmd):
    child = os.popen(cmd)
    data = child.read().splitlines()
    err = child.close()
    if err:
        raise RuntimeError, "%r failed with return code: %d" % (cmd, err)
    return data


def p4_change():
    # TODO: Rethink this signature
    #
    # I think this function should only create new change lists from the default.
    # So there should be no parameters. With the possible exception of the
    # p4 command string.

    # TODO: What if there are no files in the default change list?

    # Fallback editor is vi
    editor = "vi"

    # TODO: hard-coded hack needs fixing
    p4 = "/usr/local/bin/p4 -p 1492"

    # See if user has a favorite
    if "P4EDITOR" in os.environ:
        editor = os.environ["P4EDITOR"]
    else:
        if "EDITOR" in os.environ:
            editor = os.environ['EDITOR']

    # Capture a change template with files opened in the default change list
    change_template = run_cmd("%s change -o" % p4)

    # Create a temp file and dump the p4 change to it.
    change_form = tempfile.NamedTemporaryFile(mode="w", delete=False)
    for line in change_template:
        change_form.write(line + "\n")
    change_form.close()
    # print change_form.name

    # Open the file in the users editor
    os.system("%s %s" % (editor, change_form.name))

    # The user may have changed their mind, so see if the file changed at all.
    f = open(change_form.name, "r")
    new_change_form = [s.rstrip() for s in f.readlines()]
    f.close()

    if change_template == new_change_form:
        print "No changes made."
        change = None
    else:
        # Feed form to p4 change and capture the output
        change_output = run_cmd("%s change -i < %s" % (p4, change_form.name))
        change = change_output[0].split()[1]

    # Clean up
    os.unlink(change_form.name)

    return change


if __name__ == "__main__":
    change = p4_change()
    print change
