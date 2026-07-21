.PHONY: install ingest-batch ingest-api stream quality dbt scorecard test lint

install:
	pip install -r requirements.txt

ingest-batch:
	python -m ingest.batch_tlc --year 2024 --month 1

ingest-api:
	python -m ingest.api_weather --date 2024-01-15

stream:
	python -m ingest.stream_producer --rate 5 --seconds 60 & \
	python -m ingest.stream_consumer --batch-size 200

dbt:
	cd dbt && dbt deps && dbt seed && dbt run

quality:
	cd dbt && dbt test
	python -m quality.expectations.run_suite

scorecard:
	python -m scorecard.generate --out scorecard/SCORECARD.md --min-score 70

test:
	pytest tests/ -q

lint:
	ruff check .