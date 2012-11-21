help:
	@echo Targets: new, stomp, submit, run

new:
	@mv .git dotgit
	@p4 edit readme.txt
	@echo "Testing 1, 2, 3" >> readme.txt
	@./rb.py new
	@mv dotgit .git

stomp:
	@p4 edit relnotes.txt
	@echo "Please release me let me go!" >> relnotes.txt
	@p4 submit -d "Get this in before that sallan guy."

submit:
	@echo Need an RB id number so call rb.py directly

run:
	@./rb.py repos
	@./rb.py show user sallan
	@./rb.py show review 3
