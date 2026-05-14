.PHONY: test smoke clean

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

smoke:
	cp reproguard.yaml.example reproguard.yaml
	python3 reproguard.py --project-root . --summary-json || true

clean:
	rm -f reproguard.contract.json reproguard.report.json reproguard.report.md
	rm -rf artifacts __pycache__ tests/__pycache__
