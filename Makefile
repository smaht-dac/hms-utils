config:
	pip install poetry==1.8.3

build:
	poetry install

update: config
	poetry update
	make build

lint:
	flake8

test:
	poetry run pytest -vv

clean:
	find . -name .pytest_cache -exec rm -rf {} +
	find . -name __pycache__ -exec rm -rf {} +

publish: clean
	poetry run publish-to-pypi

publish-for-ga:
	pip install dcicutils
	python -m dcicutils.scripts.publish_to_pypi --noconfirm
