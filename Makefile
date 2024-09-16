config:
	pip install poetry==1.8.3

build:
	poetry install

update: config
	poetry update
	make build

lint:
	flake8 --exclude tmp --exclude .tmp

test:
	poetry run pytest -vv

testv:
	poetry run pytest -vv -s

clean:
	find . -name .pytest_cache -exec rm -rf {} +
	find . -name __pycache__ -exec rm -rf {} +
	rm -rf dist

publish: clean
	poetry run publish-to-pypi

publish-for-ga:
	pip install dcicutils
	python -m dcicutils.scripts.publish_to_pypi --noconfirm

leaks:
	# Install this tool with: brew install gitleaks
	# The default .gitleaks.toml file here was gotten from:
	# https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml
	# Added an S3 encrypt ID value (e.g. 271230a3-ead1-4f5a-94ce-0f2347f84a95)
	# which is NOT actually a secret value; and was referenced in a test data file.
	gitleaks detect --source . --verbose
