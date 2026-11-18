"""Serverless Spark entry point: write every staging table for one as-of date.

The simulation and fact builders are plain pandas functions (unit-tested locally); Spark only
parallelises them across properties and writes Delta tables.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from esa_resstay_demo.data.calendar import build_dim_date
from esa_resstay_demo.data.config import GenConfig, check_story_window, yesterday_in_new_york
from esa_resstay_demo.data.facts import (
    DayLookup, build_fact_actual_stay, build_fact_property_statistics, build_reservations,
)
from esa_resstay_demo.data.portfolio import build_portfolio
from esa_resstay_demo.data.reference import (
    SimReference, build_dim_channel, build_dim_crm_account, build_dim_los, build_dim_promotion,
    build_dim_rate_segment, build_dim_room_type, build_sim_reference,
)
from esa_resstay_demo.data.simulate import EVENTS_DDL, simulate_property

GENERATOR_VERSION = "1"
EVENTS_TABLE = "_sim_events"
PROPERTY_BUILDERS = {
    "fact_actual_stay": lambda ev, prop, cfg, days: build_fact_actual_stay(ev, cfg, days),
    "fact_property_statistics": lambda ev, prop, cfg, days: build_fact_property_statistics(ev, prop, cfg, days),
    "fact_reservation_summary": lambda ev, prop, cfg, days: build_reservations(ev, cfg, days)[0],
    "dim_reservation": lambda ev, prop, cfg, days: build_reservations(ev, cfg, days)[1],
}


def build_dimension_frames(cfg: GenConfig) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, SimReference]:
    """Every dimension and bridge frame, the per-property simulation inputs, and the simulation reference."""
    accounts = build_dim_crm_account(cfg)
    portfolio = build_portfolio(cfg)
    frames = {
        "dim_date": build_dim_date(cfg), "dim_channel": build_dim_channel(cfg),
        "dim_rate_segment": build_dim_rate_segment(cfg), "dim_promotion": build_dim_promotion(cfg),
        "dim_room_type": build_dim_room_type(cfg), "dim_los": build_dim_los(cfg), "dim_crm_account": accounts,
        **portfolio.frames(),
    }
    return frames, portfolio.sim_inputs, build_sim_reference(accounts)


def build_property_frames(events: pd.DataFrame, prop: dict, cfg: GenConfig, days: DayLookup) -> dict[str, pd.DataFrame]:
    return {name: builder(events, prop, cfg, days) for name, builder in PROPERTY_BUILDERS.items()}


def run_info_frame(cfg: GenConfig) -> pd.DataFrame:
    return pd.DataFrame([{
        "as_of_date": cfg.as_of_date, "story_anchor_date": cfg.story_anchor_date,
        "history_start_date": cfg.history_start_date, "sim_start_date": cfg.sim_start_date,
        "seed": cfg.seed, "scale_properties": cfg.scale_properties,
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None), "generator_version": GENERATOR_VERSION,
    }])


def schema_ddl(columns: list[list[str]]) -> str:
    return ", ".join(f"`{name}` {spark_type}" for name, spark_type in columns)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the ESA ResStay demo staging tables")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--staging-schema", required=True)
    parser.add_argument("--staging-schema-file", required=True, help="build/staging_schema.json in the bundle files")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD; empty means yesterday in America/New_York")
    parser.add_argument("--story-anchor", default="", help="YYYY-MM-DD recorded in the deployment manifest")
    parser.add_argument("--seed", default="20261117")
    parser.add_argument("--scale", default="600")
    parser.add_argument("--partitions", default="64")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> GenConfig:
    if not args.story_anchor:
        raise SystemExit("--story-anchor is required; deploy.py passes the manifest's story_anchor_date")
    as_of = date.fromisoformat(args.as_of) if args.as_of else yesterday_in_new_york()
    anchor = date.fromisoformat(args.story_anchor)
    try:
        check_story_window(as_of, anchor)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return GenConfig(as_of_date=as_of, story_anchor_date=anchor, seed=int(args.seed), scale_properties=int(args.scale))


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    args = parse_args(argv)
    cfg = config_from_args(args)
    partitions = int(args.partitions)
    spark = SparkSession.builder.getOrCreate()
    schemas = json.loads(Path(args.staging_schema_file).read_text())

    def table(name: str) -> str:
        return f"`{args.catalog}`.`{args.staging_schema}`.`{name}`"

    def write(sdf, name: str) -> None:
        sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table(name))

    frames, sim_inputs, sim = build_dimension_frames(cfg)
    for name, pdf in frames.items():
        columns = [c for c, _ in schemas[name]]
        write(spark.createDataFrame(pdf[columns], schema=schema_ddl(schemas[name])), name)

    def simulate_batches(batches):
        for batch in batches:
            for prop in batch.to_dict("records"):
                yield simulate_property(prop, cfg, sim)

    properties = spark.createDataFrame(sim_inputs)
    write(properties.repartition(partitions, "bk_property_id").mapInPandas(simulate_batches, EVENTS_DDL), EVENTS_TABLE)
    events = spark.table(table(EVENTS_TABLE))
    prop_by_id = {p["bk_property_id"]: p for p in sim_inputs.to_dict("records")}

    for name, builder in PROPERTY_BUILDERS.items():
        columns = [c for c, _ in schemas[name]]

        def build(batches, builder=builder, columns=columns):
            days = DayLookup(cfg)
            batch_list = list(batches)
            if not batch_list:
                return
            pdf = pd.concat(batch_list, ignore_index=True)
            for pid, group in pdf.groupby("bk_property_id", sort=True):
                out = builder(group.reset_index(drop=True), prop_by_id[pid], cfg, days)
                if len(out):
                    yield out[columns]

        write(events.repartition(partitions, "bk_property_id").mapInPandas(build, schema_ddl(schemas[name])), name)

    write(spark.createDataFrame(run_info_frame(cfg)), "run_info")
    print(f"Generated staging tables for as-of {cfg.as_of_date} (anchor {cfg.story_anchor_date}, "
          f"{cfg.scale_properties} properties)")


if __name__ == "__main__":
    main()
