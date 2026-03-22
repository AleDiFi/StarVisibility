"""
Top-level planning orchestrator for StarVisibility.

The Planner class is the single entry point for the business logic layer.
It:
  1. Loads the star catalog (VizieR or local)
  2. Generates time slots from the campaign configuration
  3. Runs the per-slot, per-sector scheduling loop
  4. Returns a PlanningResult ready for export or GUI display

The GUI calls start_planning() in a background thread and receives
progress updates via a callback.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from src.astro.catalog_service import load_catalog
from src.astro.observer import build_earth_location
from src.core.scheduler import ProgressCallback, run_scheduler
from src.core.timeslots import generate_time_slots
from src.models.domain import AppConfig, PlanningResult, StarCandidate
from src.utils.logging_utils import get_logger

log = get_logger("planner")


class Planner:
    """
    Orchestrates the full planning pipeline.

    Usage
    -----
    planner = Planner(config)
    result  = planner.run(progress_callback=my_fn)
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._catalog: Optional[List[StarCandidate]] = None

    # ------------------------------------------------------------------
    def load_catalog(self, force_refresh: bool = False) -> int:
        """
        Load (or reload) the star catalog.

        Returns the number of stars loaded.
        Caches the result in self._catalog so run() does not repeat the query.
        """
        log.info(
            "Loading catalog: source=%s, vmag_limit=%.1f",
            self.config.catalog_source,
            self.config.catalog_vmag_limit,
        )
        self._catalog = load_catalog(
            source=self.config.catalog_source,
            vmag_limit=self.config.catalog_vmag_limit,
            local_path=self.config.local_catalog_path,
            force_refresh=force_refresh,
        )
        log.info("Catalog loaded: %d stars", len(self._catalog))
        return len(self._catalog)

    # ------------------------------------------------------------------
    def run(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        force_catalog_refresh: bool = False,
    ) -> PlanningResult:
        """
        Execute the full planning pipeline and return a PlanningResult.

        Parameters
        ----------
        progress_callback : optional callable(current, total, message)
        force_catalog_refresh : re-download catalog even if cache exists
        """
        # 1. Catalog
        if self._catalog is None or force_catalog_refresh:
            self.load_catalog(force_refresh=force_catalog_refresh)

        if not self._catalog:
            raise RuntimeError(
                "The star catalog is empty. "
                "Check catalog source settings or network connectivity."
            )

        # 2. Time slots
        log.info("Generating time slots …")
        slots = generate_time_slots(self.config)
        log.info("Generated %d time slots across %d nights.", len(slots),
                 len(set(s.night_label for s in slots)))

        if not slots:
            raise RuntimeError(
                "No time slots were generated. "
                "Check that start_night ≤ end_night and that the night "
                "window (sunset → sunrise) is valid."
            )

        # 3. Observer location
        location = build_earth_location(self.config.observatory)

        # 4. Scheduling loop
        log.info("Starting scheduling loop …")
        result = run_scheduler(
            config=self.config,
            all_stars=self._catalog,
            slots=slots,
            location=location,
            progress_callback=progress_callback,
        )

        return result
