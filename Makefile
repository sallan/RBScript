help:
	@echo Targets: new, stomp, conflict, submit, run, p4d

new:
	@p4 edit readme.txt
	@echo "Testing 1, 2, 3" >> readme.txt
	@./rb.py create --publish -u sallan

stomp:
	@p4 edit relnotes.txt
	@echo "Please release me let me go!" >> relnotes.txt
	@p4 submit -d "Get this in before that sallan guy."

conflict:
	@p4 sync readme.txt#1
	@p4 edit readme.txt
	@echo "Causing a conflict" >> readme.txt
	@./rb.py new

submit:
	@echo Need an RB id number so call rb.py directly


run:
	@./rb.py repos
	@./rb.py show user sallan
	@./rb.py show review 3

p4d:
	@/usr/local/bin/p4d -r $$(pwd)/P4Test_Server/PerforceSample -p buffy:1492 -d
