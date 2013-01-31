.PHONY: shelve unshelve help new stomp conflict p4d

help:
	@echo Targets: new, stomp, conflict, p4d

new:
	@p4 edit readme.txt
	@echo "Testing 1, 2, 3" >> readme.txt
	@./rb-2.0 create --tp sallan --publish

stomp:
	@p4 edit relnotes.txt
	@echo "Please release me let me go!" >> relnotes.txt
	@p4 submit -d "Get this in before that sallan guy."

conflict:
	@p4 sync readme.txt#1
	@p4 edit readme.txt
	@echo "Causing a conflict" >> readme.txt
	@./rb-2.0 create --tp sallan --publish

shelve:
	@p4 edit relnotes.txt
	@echo "Create a shelve" >> relnotes.txt
	@./rb-2.0 create --shelve

pshelve:
	@p4 edit relnotes.txt
	@echo "Create a shelve" >> relnotes.txt
	./rb-2.0 rr create --tp sallan --publish --shelve

p4d:
	@/usr/local/bin/p4d -r $$(pwd)/P4Test_Server/PerforceSample -p buffy:1492 -d
