#!/usr/bin/python
from rbtools.api.client import RBClient

client = RBClient("http://localhost")
client.login("sallan", "sallan")
root = client.get_root()
root.get_repositories().create(name='perforce', tool="Perforce", path="localhost:1492")

