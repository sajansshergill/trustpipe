.PHONY: install ingest-batch ingest-api stream stream-smoke quality quality-local dbt dbt-parse scorecard test lint run app-status preflight-snowflake

install:
	pip install -r requirements.txt

ingest-batch:
	python -m config.preflight --snowflake
	python -m ingest.batch_tlc --year 2024 --month 1

ingest-api:
	python -m config.preflight --snowflake
	python -m ingest.api_weather --date 2024-01-15

stream:
	python -m config.preflight --snowflake
	python -m ingest.stream_producer --rate 5 --seconds 60 & \
	python -m ingest.stream_consumer --batch-size 200

stream-smoke:
	python -m ingest.stream_smoke --count 5 --timeout-s 20

dbt:
	python -m config.preflight --snowflake
	cd dbt && dbt deps && dbt seed && dbt run

quality:
	python -m config.preflight --snowflake
	cd dbt && dbt test
	python -m quality.expectations.run_suite

quality-local: test lint scorecard dbt-parse

dbt-parse:
	SNOWFLAKE_ACCOUNT=dummy SNOWFLAKE_USER=dummy SNOWFLAKE_PASSWORD=dummy dbt parse --project-dir dbt --profiles-dir dbt --no-partial-parse

scorecard:
	python -m scorecard.generate --out scorecard/SCORECARD.md --min-score 70

test:
	python -m pytest tests/ -q

lint:
	ruff check .

run:
	docker compose up -d zookeeper kafka airflow

app-status:
	docker compose ps

preflight-snowflake:
	python -m config.preflight --snowflake