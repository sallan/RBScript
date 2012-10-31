#!/usr/bin/env python
import os
import sys
import argparse
import shutil

class SampleDepot:

    def __init__(self, tarball, parent_dir, p4port=1492):
        self.parent_dir = os.path.abspath(parent_dir)
        self.p4root = os.path.join(self.parent_dir, "PerforceSample")
        self.p4port = p4port
        self.tarball = tarball
        self.p4d = "/usr/local/bin/p4d -r %s" % self.p4root
        self.p4  = "/usr/local/bin/p4 -p %d" % self.p4port
        self.start_cmd = "%s -p %d -d" % (self.p4d, self.p4port)
        self.stop_cmd = "%s admin stop" % self.p4


    def server_start(self):
        os.system(self.start_cmd)
        print "Server started on port: %d" % self.p4port


    def server_stop(self):
        os.system(self.stop_cmd)


#    def server_delete(self):

    def unpack_depot(self):
        os.chdir(self.parent_dir)
        os.system("tar xzf %s" % self.tarball)


    def server_restore(self):
        os.system("%s -jr %s" % (self.p4d, os.path.join(self.p4root, "checkpoint")))
        os.system("%s -xu" % self.p4d)

    def info(self):
        os.system("%s info" % self.p4)

# TODO: cruft to remove
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

    p4 = SampleDepot(tarfile, destination)
    p4.server_start()
    p4.info()
    p4.server_stop()


if __name__ == "__main__":
    main()
