#!/usr/bin/env python
import os
import argparse
import shutil
import subprocess
import time


class SampleDepot:
    def __init__(self, tarball, parent_dir, p4port=1492):
        self.parent_dir = os.path.abspath(parent_dir)
        self.p4root = os.path.join(self.parent_dir, "PerforceSample")
        self.p4port = p4port
        self.tarball = tarball
        self.p4d = "/usr/local/bin/p4d -r %s" % self.p4root
        self.p4 = "/usr/local/bin/p4 -p %d" % self.p4port
        self.start_cmd = "%s -p %d -d" % (self.p4d, self.p4port)
        self.stop_cmd = "%s admin stop" % self.p4


    def server_start(self):
        os.system(self.start_cmd)
        print "Server started on port: %d" % self.p4port


    def server_stop(self):
        try:
            # self.info()
            subprocess.call(["/usr/local/bin/p4", "-p", "1492", "admin", "stop"])
            # TODO: should probably check error code here
            print "Server stopped on port: %s " % self.p4port
        except subprocess.CalledProcessError:
            print "Already stopped?"

    def server_delete(self):
        p4root = self.p4root
        if os.path.exists(p4root):
            if os.path.isfile(p4root):
                raise RuntimeError("%s is a file! Exiting." % p4root)
            else:
                if os.path.isdir(p4root):
                    # assume it's a sample depot and try to stop the server first
                    print "%s already exists. Attempting to stop server..." % p4root
                    self.server_stop()
                    # Pause for a bit to let server shut down or you won't be able to delete
                    time.sleep(5)

                    print "Deleting %s" % p4root
                    shutil.rmtree(p4root)
                else:
                    raise RuntimeError(
                        "p4root '%s' exists, but is not a file or directory! What the heck is it?" % p4root)


    def server_install(self):
        if os.path.isdir(self.parent_dir):
            self.server_delete()
        else:
            os.makedirs(self.parent_dir)

        # Move to destination dir and unpack tarball
        os.chdir(self.parent_dir)
        os.system("tar xzf %s" % self.tarball)

        # Restore checkpoint and upgrade db files to our server
        os.system("%s -jr %s" % (self.p4d, os.path.join(self.p4root, "checkpoint")))
        os.system("%s -xu" % self.p4d)


    def info(self):
        subprocess.check_output(["/usr/local/bin/p4", "-p", "1492", "info"])


def parse_options():
    parser = argparse.ArgumentParser(description="Create a sample perforce depot.")
    parser.add_argument("dir", help="Directory to install depot - will overwrite all contents.")
    parser.add_argument("tarfile", help="Gzipped tar file containing contents of sample depot.")
    parser.add_argument("-p", "--prompt", action="store_true", help="Prompt if destination directory exists.")
    return parser.parse_args()


def main():
    args = parse_options()

    destination = os.path.abspath(args.dir)
    tarfile = os.path.abspath(args.tarfile)

    p4 = SampleDepot(tarfile, destination)
    p4.server_install()
    p4.server_start()
#    p4.info()


if __name__ == "__main__":
    main()
