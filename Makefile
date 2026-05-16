.PHONY: test smoke clean

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

smoke:
	@TMPDIR=$$(mktemp -d 2>/dev/null || mktemp -d -t reproguard-smoke); \
	cp reproguard.yaml.example "$$TMPDIR/reproguard.yaml"; \
	python3 reproguard.py --project-root . --config "$$TMPDIR/reproguard.yaml" --output-dir "$$TMPDIR" --summary-json || true; \
	rm -rf "$$TMPDIR"

clean:
	rm -f reproguard.contract.json reproguard.report.json reproguard.report.md
	rm -rf artifacts __pycache__ tests/__pycache__
