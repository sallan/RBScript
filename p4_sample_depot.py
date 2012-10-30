#!/usr/bin/env python
import os
import sys
import argparse
import shutil


def clean_p4root(p4root, ask):
    if os.path.exists(p4root):
        if os.path.isfile(p4root):
            raise RuntimeError("P4Root '%s' exists as a file. Exiting." % p4root)
        else:
            if os.path.isdir(p4root):
                if ask:
                    # TODO: prompt would go here
                    pass

                # Delete directory and all contents
                print "Deleting old P4Root '%s'" % p4root
                shutil.rmtree(p4root)
            else:
                raise RuntimeError("P4Root '%s' exists, but is not a file or directory!" % p4root)


def unpack_depot(tarfile, destination):
    os.chdir(destination)
    os.system("tar xzf %s" % tarfile)


def start_server(p4root, p4port=1492):
    checkpoint = os.path.join(p4root, "checkpoint")
    p4d = "/usr/local/bin/p4d"

    os.system("%s -r %s -jr %s" % (p4d, p4root, checkpoint))
    os.system("%s -r %s -xu" % (p4d, p4root))
    os.system("%s -d -r %s -p %d" % (p4d, p4root, p4port))
    print "Server started on port: %d" % p4port


def parse_options():
    parser = argparse.ArgumentParser(description="Create a sample perforce depot.")
    parser.add_argument("dir", help="Directory to install depot - will overwrite all contents.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Do I need any options?")
    parser.add_argument("-p", "--prompt", action="store_true", help="Prompt if destination directory exists.")
    return parser.parse_args()


def main():
    tarfile = os.path.join(os.path.expanduser("~"), "Projects", "sample-depot", "p4sample-depot.tar.gz")
    args = parse_options()

    destination = os.path.abspath(args.dir)
    p4root = os.path.join(destination, "PerforceSample")

    # If server already in p4root, need to stop it and delete it.
    clean_p4root(p4root, args.prompt)

    # Unpack tarball in destination directory
    unpack_depot(tarfile, destination)

    # Start server
    # TODO: add p4port argument
    start_server(p4root)


if __name__ == "__main__":
    main()
