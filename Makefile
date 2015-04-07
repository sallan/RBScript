.PHONY: tags

unit-test:
	@./test_post.py

func-test: p4-repo rb-site
	./func_tests.py

p4-repo:
	@(set -e; \
          ./p4_sample_depot.py  $$(pwd)/P4Test_Server p4-sample-depot.tar.gz; \
          p4 client -i < p4client-template; \
          p4 sync -f; \
	)

rb-site:
	@sudo ./rb-sqlite-sandbox.sh localhost rb
	sleep 5
	./addrepo.py

p4d:
	@/usr/local/bin/p4d -r $$(pwd)/P4Test_Server/PerforceSample -p localhost:1492 -d


tags:
	@/usr/local/bin/ctags -R


