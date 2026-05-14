"""
pipeline/base.py — BasePipeline abstract base class.

All pipeline classes extend BasePipeline and only implement execute().
BasePipeline handles:
  - Creating a RUNNING EtlRun row at entry (via start_etl_run from crud.py)
  - Calling execute()
  - Marking the EtlRun as COMPLETED / PARTIAL / FAILED at exit
  - Catching unhandled exceptions and recording them in error_msg

Usage:
    class AmfiNavPipeline(BasePipeline):
        pipeline_name = "amfi_nav"

        async def execute(self) -> PipelineResult:
            # fetch + upsert logic here
            return PipelineResult(records_in=14500, records_out=14500)

    async def run_amfi_nav():
        async with AsyncSessionLocal() as db:
            result = await AmfiNavPipeline(db).run()
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import start_etl_run, finish_etl_run

logger = logging.getLogger(__name__)


class PipelineResult:
    """Returned by every pipeline's execute() method."""

    def __init__(
        self,
        records_in: int = 0,
        records_out: int = 0,
        error_msg: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.records_in = records_in
        self.records_out = records_out
        self.error_msg = error_msg
        self.metadata = metadata or {}
        self.success = error_msg is None


class BasePipeline(ABC):
    """
    Abstract base class for all ingestion pipelines.

    Subclasses must:
      1. Set pipeline_name (must match the id used in scheduler.py)
      2. Implement execute() returning a PipelineResult

    Subclasses must NOT catch their own top-level exceptions — BasePipeline
    handles those and maps them to FAILED status in etl_runs.
    """

    pipeline_name: str = ""

    def __init__(
        self,
        db: AsyncSession,
        entity_id: Optional[str] = None,
        triggered_by: str = "scheduler",
    ):
        self.db = db
        self.entity_id = entity_id
        self.triggered_by = triggered_by
        self._run_id: Optional[int] = None

    @abstractmethod
    async def execute(self) -> PipelineResult:
        """
        Core pipeline logic.

        Must return a PipelineResult.
        Must NOT catch its own top-level exceptions — BasePipeline handles that.
        For per-record failures, catch internally and count them but still return
        a PipelineResult (status will be PARTIAL if error_msg is set).
        """
        ...

    async def run(self) -> PipelineResult:
        """
        Entry point called by the scheduler or manual trigger.
        Wraps execute() with EtlRun lifecycle logging.
        """
        if not self.pipeline_name:
            raise ValueError(
                f"{self.__class__.__name__} must set pipeline_name class attribute"
            )

        # ── Start run ────────────────────────────────────────────────────────
        run, created = await start_etl_run(
            self.db,
            pipeline_name=self.pipeline_name,
            entity_id=self.entity_id,
            triggered_by=self.triggered_by,
        )

        if not created:
            logger.warning(
                f"[{self.pipeline_name}] already RUNNING "
                f"(run_id={run.id if run else '?'}) — skipping duplicate execution"
            )
            return PipelineResult(error_msg="Already running — skipped")

        self._run_id = run.id
        logger.info(f"[{self.pipeline_name}] started  run_id={run.id}")

        # ── Execute ──────────────────────────────────────────────────────────
        try:
            result = await self.execute()
            status = "COMPLETED" if result.success else "PARTIAL"
        except Exception as exc:
            logger.exception(f"[{self.pipeline_name}] unhandled exception")
            result = PipelineResult(error_msg=str(exc)[:1000])
            status = "FAILED"

        # ── Finish run ───────────────────────────────────────────────────────
        await finish_etl_run(
            self.db,
            run_id=self._run_id,
            status=status,
            records_in=result.records_in,
            records_out=result.records_out,
            error_msg=result.error_msg,
        )

        logger.info(
            f"[{self.pipeline_name}] {status}  "
            f"in={result.records_in}  out={result.records_out}"
            + (f"  error={result.error_msg}" if result.error_msg else "")
        )

        if status == "FAILED":
            logger.error(
                f"PIPELINE FAILED: {self.pipeline_name} "
                f"entity={self.entity_id}  error={result.error_msg}"
            )

        return result
