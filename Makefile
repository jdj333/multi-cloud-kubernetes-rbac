PYTHON ?= python3
CONTEXT ?= kind-rbac-demo

.PHONY: test fmt validate demo clean-demo
test:
	$(PYTHON) -m unittest discover -s tests -v

fmt:
	terraform fmt -check -recursive

validate:
	@set -eu; for dir in terraform/*/; do \
		terraform -chdir=$$dir init -backend=false -input=false; \
		terraform -chdir=$$dir validate; \
	done

demo:
	kind create cluster --name rbac-demo --wait 120s
	kubectl --context $(CONTEXT) apply -f kubernetes/
	kubectl --context $(CONTEXT) create namespace team-b
	$(PYTHON) scripts/check_access.py --context $(CONTEXT) --as-user demo-reader --group platform-readers

clean-demo:
	kind delete cluster --name rbac-demo
