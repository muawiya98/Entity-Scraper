"""End-to-end pipeline: search -> scrape -> extract -> store -> export.

Runs inside a background thread so the web UI stays responsive.  Progress is
written back to the ``searches`` table and polled by the front end.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import config
from core import database, exporter, llm, safety
from core.scraper import SiteScraper
from core.search import search_websites

log = logging.getLogger(__name__)


def run_pipeline(search_id: int) -> None:
    search = database.get_search(search_id)
    if not search:
        log.error("Search %s not found", search_id)
        return

    query = search["query"]
    location = search.get("location") or ""
    entity_type = search.get("entity_type") or ""
    max_results = search.get("max_results") or 10

    try:
        database.update_search(
            search_id, status="running", progress=2, message="Searching the web…"
        )

        results = search_websites(
            query=query,
            location=location,
            entity_type=entity_type,
            max_results=max_results,
            region=config.DEFAULT_REGION,
        )

        if not results:
            database.update_search(
                search_id,
                status="completed",
                progress=100,
                message="No websites found for this query.",
                results_count=0,
                completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            exporter.export_search(search_id)
            return

        database.update_search(
            search_id,
            progress=10,
            message=f"Found {len(results)} websites. Visiting each…",
        )

        scraper = SiteScraper(region=config.DEFAULT_REGION)
        total = len(results)
        stored = 0

        for index, result in enumerate(results, start=1):
            database.update_search(
                search_id,
                progress=10 + int(85 * index / total),
                message=f"Scraping {index}/{total}: {result.domain}",
            )
            try:
                record = scraper.scrape(result.url)
            except Exception as exc:  # noqa: BLE001
                log.warning("Scrape failed for %s: %s", result.url, exc)
                record = None

            if record:
                # Carry over the search snippet as a fallback description.
                if not record.get("description"):
                    record["description"] = result.snippet
                record.setdefault("meta", {})["search_title"] = result.title
                record.setdefault("meta", {})["search_snippet"] = result.snippet
                record["meta"]["relevance_score"] = safety.record_relevance_score(
                    record,
                    query=query,
                    location=location,
                    entity_type=entity_type,
                )
                if not safety.record_is_relevant(
                    record,
                    query=query,
                    location=location,
                    entity_type=entity_type,
                ):
                    log.info("Skipping low-relevance record: %s", result.url)
                    continue
                # The query is a people-data extraction request: an entity that
                # yields no usable person (name + position/email/phone) is
                # dropped, so nothing is returned for it.
                if not safety.has_people_data(record):
                    log.info("Skipping record with no people data: %s", result.url)
                    continue
                if llm.enabled():
                    verdict = llm.validate_entity_record(record, query, location, entity_type)
                    if verdict:
                        record["meta"]["llm_relevance_reason"] = verdict.get("reason", "")
                        if verdict.get("relevant") is False:
                            log.info("LLM rejected record %s: %s", result.url, verdict.get("reason"))
                            continue
                database.insert_entity(search_id, record)
                stored += 1

        path = exporter.export_search(search_id)
        database.update_search(
            search_id,
            status="completed",
            progress=100,
            message=f"Done. {stored} entities saved. JSON: {path}",
            results_count=stored,
            completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        log.info("Search %s complete: %s entities", search_id, stored)

    except Exception as exc:  # noqa: BLE001
        log.exception("Pipeline failed for search %s", search_id)
        database.update_search(
            search_id,
            status="failed",
            message=f"Error: {exc}",
            completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
