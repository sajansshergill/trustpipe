"""Central configuration. All secrets come from the environment, never hardcoded."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_PATH = REPO_ROOT / "config" / "contracts.yml"


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str
    user: str
    password: str
    role: str
    warehouse: str
    database: str
    schema: str

    @classmethod
    def from_env(cls) -> "SnowflakeConfig":
        def req(key: str) -> str:
            val = os.environ.get(key)
            if not val:
                raise EnvironmentError(f"Missing required env var: {key}")
            return val

        return cls(
            account=req("SNOWFLAKE_ACCOUNT"),
            user=req("SNOWFLAKE_USER"),
            password=req("SNOWFLAKE_PASSWORD"),
            role=os.environ.get("SNOWFLAKE_ROLE", "TRUSTPIPE_LOADER"),
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "TRUSTPIPE_WH"),
            database=os.environ.get("SNOWFLAKE_DATABASE", "TRUSTPIPE"),
            schema=os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
        )


@dataclass(frozen=True)
class KafkaConfig:
    bootstrap_servers: str
    topic: str

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        return cls(
            bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092"),
            topic=os.environ.get("KAFKA_TOPIC", "ride_stream"),
        )


@lru_cache(maxsize=1)
def load_contracts() -> dict:
    """Parse the data-contract definitions once and cache them."""
    with open(CONTRACTS_PATH) as fh:
        return yaml.safe_load(fh)


def get_contract(name: str) -> dict:
    contracts = load_contracts()
    if name not in contracts:
        raise KeyError(f"No contract defined for source '{name}'")
    return contracts[name]