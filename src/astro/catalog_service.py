"""
Catalog service for StarVisibility.

Provides two adapters:
  1. VizierCatalogAdapter  – queries the Hipparcos catalog (I/239/hip_main)
     via astroquery.  Results are cached locally as CSV so subsequent runs
     are instant even without internet access.
  2. LocalCatalogAdapter   – reads a user-supplied CSV (or FITS) file.

Both adapters return a list of StarCandidate objects.

Column requirements for user-supplied local CSV:
  Required : ra_deg, dec_deg, vmag
  Optional : star_id, star_name, spectral_type, catalog_source

If star_id / star_name are absent they are generated from row index.

Hipparcos cache CSV columns (internal format):
  HIP, ra_deg, dec_deg, vmag, spectral_type, star_name
"""

from __future__ import annotations

import csv
import logging
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from src.config.settings import (
    HIPPARCOS_CACHE_FILE,
    VIZIER_CATALOG_ID,
    VIZIER_COLUMNS,
)
from src.models.domain import StarCandidate
from src.utils.logging_utils import get_logger

# All magnitude columns written/read in the CSV cache.
# Must match the fields in StarCandidate.to_dict().
_CACHE_FIELDS = [
    "star_id", "star_name", "ra_deg", "dec_deg",
    "vmag", "spectral_type", "catalog_source",
    "umag", "bmag", "rmag", "imag", "jmag", "hmag", "kmag",
]

# Johnson B from Tycho BTmag/VTmag using the ESA Hipparcos vol.1 formula.
# B_J ≈ V_J + 0.850 * (BT - VT)  (valid for most spectral types at |BT-VT|<0.5)
_BT_VT_COEFF = 0.850


def _bt_vt_to_johnson_b(bt: float, vt: float) -> float:
    """Convert Tycho BT/VT to approximate Johnson B.

    Uses the linear relation B_J ≈ V_J + 0.850*(BT - VT) from the ESA
    Hipparcos & Tycho Catalogues (ESA SP-1200, vol. 1, §1.3).
    VT is a close enough proxy for V_J here.
    """
    return vt + _BT_VT_COEFF * (bt - vt)


def _safe_float(val) -> Optional[float]:
    """Return float(val) or None if the value is masked/missing."""
    try:
        v = float(val)
        import math
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


log = get_logger("catalog")

_BRIGHT_NAMES: dict[int, str] = {
    24436: "Rigel", 27989: "Betelgeuse", 37279: "Procyon", 32349: "Sirius",
    49669: "Regulus", 65378: "Mizar", 67301: "Alcor", 69673: "Arcturus",
    71683: "α Cen A", 71681: "α Cen B", 80763: "Antares", 91262: "Vega",
    97649: "Altair", 102098: "Deneb", 113368: "Fomalhaut", 677: "α And",
    3179: "β And", 11767: "Polaris", 15863: "Achernar", 21421: "Aldebaran",
    25336: "Castor", 25428: "Pollux", 26311: "Capella", 30438: "Achernar",
    36850: "Castor", 37826: "Pollux", 50583: "Denebola", 57632: "Spica",
    60718: "Acrux", 62434: "Mimosa", 68702: "Gacrux", 84345: "Rasalhague",
    85927: "Sabik", 86032: "Rasalhague", 87937: "Barnard's Star",
    107315: "Alpheratz", 109268: "Scheat", 110893: "Markab",
    9884: "α Ari", 14135: "β Ari", 17702: "η Tau", 17847: "Alcyone",
    20889: "ε Tau", 23875: "β Tau", 28380: "Alhena", 28380: "Alhena",
    2081: "β Cas", 677: "α And (Alpheratz)",
    39429: "Alphard", 54061: "Dubhe", 57399: "Merak", 58001: "Phecda",
    59774: "Megrez", 62956: "Alioth", 65378: "Mizar", 67301: "Alcor",
    67927: "Alkaid", 70890: "Proxima Cen",
    7588: "Mirach", 3419: "γ And",
}


# ---------------------------------------------------------------------------
# VizieR adapter
# ---------------------------------------------------------------------------


class VizierCatalogAdapter:
    """
    Fetch stars from the Hipparcos catalog on VizieR with local CSV caching.

    Raises RuntimeError if the network query fails and no cache exists.
    """

    def __init__(
        self,
        vmag_limit: float = 7.5,
        cache_file: Optional[Path] = None,
    ) -> None:
        self.vmag_limit = vmag_limit
        self.cache_file = cache_file or HIPPARCOS_CACHE_FILE

    # ------------------------------------------------------------------
    def load(self, force_refresh: bool = False) -> List[StarCandidate]:
        """
        Load the catalog.  Returns cached data if available; otherwise
        queries VizieR and saves the result.
        """
        if not force_refresh and self.cache_file.exists():
            log.info("Loading Hipparcos catalog from cache: %s", self.cache_file)
            return self._load_cache()

        log.info(
            "Querying VizieR for Hipparcos stars with Vmag < %.1f …", self.vmag_limit
        )
        try:
            stars = self._query_vizier()
            self._save_cache(stars)
            log.info("Cached %d stars to %s", len(stars), self.cache_file)
            return stars
        except Exception as exc:
            log.error("VizieR query failed: %s", exc)
            if self.cache_file.exists():
                log.warning("Falling back to existing (possibly stale) cache.")
                return self._load_cache()
            raise RuntimeError(
                f"VizieR query failed and no cache exists.\nError: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    def _query_vizier(self) -> List[StarCandidate]:
        """Perform the VizieR query and cross-match with 2MASS.

        Steps
        -----
        1. Query Hipparcos (I/239/hip_main) for HIP, RA, Dec, Vmag,
           BTmag, VTmag, SpType.
        2. Convert BTmag/VTmag to Johnson B using the ESA formula.
        3. Cross-match the resulting astropy Table against 2MASS
           (II/246/out) via astroquery.xmatch to obtain Jmag, Hmag, Kmag.
        4. Query SIMBAD in batches of 200 stars to obtain Umag, Rmag, Imag
           for the brightest stars (V < 7.5 are nearly all in SIMBAD).
        """
        from astroquery.vizier import Vizier  # lazy import

        # ---- step 1: Hipparcos via VizieR ---------------------------------
        v = Vizier(
            columns=["HIP", "RAICRS", "DEICRS", "Vmag", "BTmag", "VTmag", "SpType"],
            row_limit=-1,
        )
        v.TIMEOUT = 120

        log.info("Contacting VizieR (%s) …", VIZIER_CATALOG_ID)
        t0 = time.monotonic()
        result = v.query_constraints(
            catalog=VIZIER_CATALOG_ID,
            Vmag=f"< {self.vmag_limit}",
        )
        dt = time.monotonic() - t0
        log.info("VizieR query returned in %.1f s", dt)

        if not result or len(result) == 0:
            raise RuntimeError("VizieR returned an empty result set.")

        table = result[0]
        has_sptype = "SpType" in table.colnames
        has_bt = "BTmag" in table.colnames and "VTmag" in table.colnames

        # Build preliminary StarCandidate list and a HIP-keyed lookup dict
        stars: List[StarCandidate] = []
        hip_to_idx: dict[int, int] = {}   # HIP number → index in *stars*

        for row in table:
            try:
                hip = int(row["HIP"])
                ra = float(row["RAICRS"])
                dec = float(row["DEICRS"])
                vmag = float(row["Vmag"])
                sptype = str(row["SpType"]).strip() if has_sptype else ""
            except (ValueError, KeyError):
                continue

            # Approximate Johnson B from Tycho photometry
            bmag: Optional[float] = None
            if has_bt:
                bt = _safe_float(row["BTmag"])
                vt = _safe_float(row["VTmag"])
                if bt is not None and vt is not None:
                    bmag = _bt_vt_to_johnson_b(bt, vt)

            name = _BRIGHT_NAMES.get(hip, f"HIP {hip}")
            hip_to_idx[hip] = len(stars)
            stars.append(
                StarCandidate(
                    star_id=f"HIP {hip}",
                    star_name=name,
                    ra_deg=ra,
                    dec_deg=dec,
                    vmag=vmag,
                    catalog_source="Hipparcos",
                    spectral_type=sptype[:10] if sptype else "",
                    bmag=bmag,
                )
            )

        log.info("Hipparcos: %d stars parsed.", len(stars))

        # ---- step 2: XMatch with 2MASS to obtain J, H, K -----------------
        stars = self._enrich_with_twomass(stars, table)

        # ---- step 3: SIMBAD batch query for U, R, I -----------------------
        stars = self._enrich_with_simbad_uri(stars)

        return stars

    # ------------------------------------------------------------------
    def _enrich_with_twomass(self, stars: List[StarCandidate],
                              hip_table) -> List[StarCandidate]:
        """Cross-match the Hipparcos table against 2MASS via CDS XMatch service.

        Adds *jmag*, *hmag*, *kmag* in-place.  Returns the modified list.
        Stars without a 2MASS counterpart within 2 arcsec keep None.

        Parameters
        ----------
        stars : list already populated by _query_vizier step 1.
        hip_table : astropy Table returned by VizieR (provides positions).
        """
        try:
            from astroquery.xmatch import XMatch
            import astropy.units as u
            from astropy.table import Table as ATable
        except ImportError:
            log.warning("astroquery.xmatch not available; skipping 2MASS enrichment.")
            return stars

        try:
            log.info("XMatch: cross-matching %d stars with 2MASS …", len(stars))
            t0 = time.monotonic()

            # Build a minimal astropy Table from our star list (RA/Dec in deg)
            local_tbl = ATable(
                {
                    "star_id": [s.star_id for s in stars],
                    "ra": [s.ra_deg for s in stars],
                    "dec": [s.dec_deg for s in stars],
                },
            )

            xm = XMatch.query(
                cat1=local_tbl,
                cat2="vizier:II/246/out",   # 2MASS All-Sky Catalog of Point Sources
                max_distance=2 * u.arcsec,
                colRA1="ra",
                colDec1="dec",
            )
            dt = time.monotonic() - t0
            log.info("2MASS XMatch returned %d matches in %.1f s.", len(xm), dt)

            # Build a lookup: star_id → (Jmag, Hmag, Kmag)
            matched: dict[str, tuple] = {}
            j_col = next((c for c in xm.colnames if c in ("Jmag", "j_m")), None)
            h_col = next((c for c in xm.colnames if c in ("Hmag", "h_m")), None)
            k_col = next((c for c in xm.colnames if c in ("Kmag", "k_m")), None)

            if j_col and h_col and k_col:
                for row in xm:
                    sid = str(row["star_id"])
                    matched[sid] = (
                        _safe_float(row[j_col]),
                        _safe_float(row[h_col]),
                        _safe_float(row[k_col]),
                    )

            # Update StarCandidate objects in-place
            enriched = 0
            for star in stars:
                if star.star_id in matched:
                    star.jmag, star.hmag, star.kmag = matched[star.star_id]
                    enriched += 1

            log.info("2MASS: enriched %d/%d stars with J/H/K.", enriched, len(stars))

        except Exception as exc:
            log.warning("2MASS XMatch failed (%s); J/H/K will be None.", exc)

        return stars

    # ------------------------------------------------------------------
    def _enrich_with_simbad_uri(self, stars: List[StarCandidate],
                                 batch_size: int = 200) -> List[StarCandidate]:
        """Query SIMBAD for U, R, I magnitudes in batches.

        Sends HIP identifiers to SIMBAD in chunks of *batch_size* using
        ``Simbad.query_objects()``.  Stars without a SIMBAD cross-match
        keep None.  U and I are frequently missing for faint stars.

        Parameters
        ----------
        stars : list to enrich in-place.
        batch_size : number of identifiers per SIMBAD request.
        """
        try:
            from astroquery.simbad import Simbad
        except ImportError:
            log.warning("astroquery.simbad not available; skipping U/R/I enrichment.")
            return stars

        try:
            s = Simbad()
            s.TIMEOUT = 120
            s.add_votable_fields("flux(U)", "flux(R)", "flux(I)")

            ids = [star.star_id for star in stars]   # e.g. ["HIP 677", …]
            # Build star_id → index lookup for O(1) update
            id_to_idx = {star.star_id: i for i, star in enumerate(stars)}

            enriched = 0
            for chunk_start in range(0, len(ids), batch_size):
                chunk = ids[chunk_start: chunk_start + batch_size]
                log.info(
                    "SIMBAD U/R/I batch %d–%d of %d …",
                    chunk_start + 1,
                    chunk_start + len(chunk),
                    len(ids),
                )
                try:
                    res = s.query_objects(chunk)
                except Exception as exc:
                    log.warning("SIMBAD batch %d failed: %s", chunk_start, exc)
                    continue

                if res is None:
                    continue

                # SIMBAD returns MAIN_ID which may differ slightly;
                # match position-in-batch instead via the original identifier.
                for i, row in enumerate(res):
                    orig_id = chunk[i] if i < len(chunk) else None
                    if orig_id and orig_id in id_to_idx:
                        idx = id_to_idx[orig_id]
                        u = _safe_float(row.get("FLUX_U"))
                        r = _safe_float(row.get("FLUX_R"))
                        iv = _safe_float(row.get("FLUX_I"))
                        stars[idx].umag = u
                        stars[idx].rmag = r
                        stars[idx].imag = iv
                        if u is not None or r is not None or iv is not None:
                            enriched += 1

            log.info("SIMBAD: enriched %d/%d stars with U/R/I.", enriched, len(stars))

        except Exception as exc:
            log.warning("SIMBAD enrichment failed (%s); U/R/I will be None.", exc)

        return stars

    # ------------------------------------------------------------------
    def _save_cache(self, stars: List[StarCandidate]) -> None:
        """Persist the star list to CSV, writing all photometric bands."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CACHE_FIELDS)
            writer.writeheader()
            for s in stars:
                writer.writerow(s.to_dict())

    # ------------------------------------------------------------------
    def _load_cache(self) -> List[StarCandidate]:
        """Load all stars (including multi-band mags) from the CSV cache."""
        df = pd.read_csv(self.cache_file, dtype=str, na_filter=False)
        stars: List[StarCandidate] = []
        for _, row in df.iterrows():
            try:
                stars.append(
                    StarCandidate(
                        star_id=str(row.get("star_id", "")),
                        star_name=str(row.get("star_name", "")),
                        ra_deg=float(row["ra_deg"]),
                        dec_deg=float(row["dec_deg"]),
                        vmag=float(row["vmag"]),
                        catalog_source=str(row.get("catalog_source", "Hipparcos")),
                        spectral_type=str(row.get("spectral_type", "")),
                        umag=_safe_float(row.get("umag", "")),
                        bmag=_safe_float(row.get("bmag", "")),
                        rmag=_safe_float(row.get("rmag", "")),
                        imag=_safe_float(row.get("imag", "")),
                        jmag=_safe_float(row.get("jmag", "")),
                        hmag=_safe_float(row.get("hmag", "")),
                        kmag=_safe_float(row.get("kmag", "")),
                    )
                )
            except (ValueError, KeyError):
                continue
        log.info("Loaded %d stars from cache.", len(stars))
        return stars


# ---------------------------------------------------------------------------
# SIMBAD adapter (all bands in one query, no XMatch required)
# ---------------------------------------------------------------------------


class SimbadCatalogAdapter:
    """Fetch stars from SIMBAD providing all photometric bands (U–K).

    Uses ``astroquery.simbad.Simbad.query_criteria`` with a V-magnitude
    filter.  The requested VOTable fields include all eight standard bands.
    Stars whose primary V magnitude is unavailable are discarded.

    Cache
    -----
    Results are cached to ``.cache/simbad_vmag<limit>_cache.csv`` so that
    subsequent runs do not require network access.
    """

    def __init__(
        self,
        vmag_limit: float = 7.5,
        cache_file: Optional[Path] = None,
    ) -> None:
        self.vmag_limit = vmag_limit
        # Store in a separate file so it does not collide with the Hipparcos cache
        self.cache_file = cache_file or (
            HIPPARCOS_CACHE_FILE.parent
            / f"simbad_vmag{vmag_limit}_cache.csv"
        )

    # ------------------------------------------------------------------
    def load(self, force_refresh: bool = False) -> List[StarCandidate]:
        """Return cached stars or fetch from SIMBAD if needed."""
        if not force_refresh and self.cache_file.exists():
            log.info("Loading SIMBAD catalog from cache: %s", self.cache_file)
            return self._load_cache()

        log.info("Querying SIMBAD for stars with Vmag < %.1f …", self.vmag_limit)
        try:
            stars = self._query_simbad()
            self._save_cache(stars)
            log.info("SIMBAD cache: %d stars written to %s", len(stars), self.cache_file)
            return stars
        except Exception as exc:
            log.error("SIMBAD query failed: %s", exc)
            if self.cache_file.exists():
                log.warning("Falling back to existing SIMBAD cache.")
                return self._load_cache()
            raise RuntimeError(
                f"SIMBAD query failed and no cache exists.\nError: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    def _query_simbad(self) -> List[StarCandidate]:
        """Perform the actual SIMBAD network query.

        Requests all eight photometric bands in one call.  RA/Dec are
        returned in sexagesimal format (``RA``, ``DEC``) and converted to
        decimal degrees via :class:`astropy.coordinates.SkyCoord`.
        """
        from astroquery.simbad import Simbad
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        s = Simbad()
        s.TIMEOUT = 180
        # Request all eight standard photometric bands
        for band in ("U", "B", "V", "R", "I", "J", "H", "K"):
            s.add_votable_fields(f"flux({band})")
        s.add_votable_fields("sptype")

        log.info("Contacting SIMBAD …")
        t0 = time.monotonic()
        result = s.query_criteria(f"Vmag < {self.vmag_limit}")
        dt = time.monotonic() - t0
        log.info("SIMBAD query returned in %.1f s", dt)

        if result is None or len(result) == 0:
            raise RuntimeError("SIMBAD returned an empty result set.")

        has_sptype = "SP_TYPE" in result.colnames
        stars: List[StarCandidate] = []

        for row in result:
            # Primary V magnitude must be present
            vmag = _safe_float(row.get("FLUX_V"))
            if vmag is None:
                continue

            main_id = str(row["MAIN_ID"]).strip()
            ra_str = str(row["RA"]).strip()
            dec_str = str(row["DEC"]).strip()

            # Convert sexagesimal RA/Dec to decimal degrees
            try:
                coord = SkyCoord(
                    ra=ra_str, dec=dec_str,
                    unit=(u.hourangle, u.deg),
                    frame="icrs",
                )
                ra = float(coord.ra.deg)
                dec = float(coord.dec.deg)
            except Exception:
                continue

            sptype = str(row["SP_TYPE"]).strip() if has_sptype else ""

            stars.append(
                StarCandidate(
                    star_id=main_id,
                    star_name=main_id,
                    ra_deg=ra,
                    dec_deg=dec,
                    vmag=vmag,
                    catalog_source="SIMBAD",
                    spectral_type=sptype[:10] if sptype else "",
                    umag=_safe_float(row.get("FLUX_U")),
                    bmag=_safe_float(row.get("FLUX_B")),
                    rmag=_safe_float(row.get("FLUX_R")),
                    imag=_safe_float(row.get("FLUX_I")),
                    jmag=_safe_float(row.get("FLUX_J")),
                    hmag=_safe_float(row.get("FLUX_H")),
                    kmag=_safe_float(row.get("FLUX_K")),
                )
            )

        return stars

    # ------------------------------------------------------------------
    def _save_cache(self, stars: List[StarCandidate]) -> None:
        """Persist the SIMBAD star list to CSV (same schema as VizieR cache)."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CACHE_FIELDS)
            writer.writeheader()
            for s in stars:
                writer.writerow(s.to_dict())

    # ------------------------------------------------------------------
    def _load_cache(self) -> List[StarCandidate]:
        """Load SIMBAD stars from the CSV cache."""
        df = pd.read_csv(self.cache_file, dtype=str, na_filter=False)
        stars: List[StarCandidate] = []
        for _, row in df.iterrows():
            try:
                stars.append(
                    StarCandidate(
                        star_id=str(row.get("star_id", "")),
                        star_name=str(row.get("star_name", "")),
                        ra_deg=float(row["ra_deg"]),
                        dec_deg=float(row["dec_deg"]),
                        vmag=float(row["vmag"]),
                        catalog_source=str(row.get("catalog_source", "SIMBAD")),
                        spectral_type=str(row.get("spectral_type", "")),
                        umag=_safe_float(row.get("umag", "")),
                        bmag=_safe_float(row.get("bmag", "")),
                        rmag=_safe_float(row.get("rmag", "")),
                        imag=_safe_float(row.get("imag", "")),
                        jmag=_safe_float(row.get("jmag", "")),
                        hmag=_safe_float(row.get("hmag", "")),
                        kmag=_safe_float(row.get("kmag", "")),
                    )
                )
            except (ValueError, KeyError):
                continue
        log.info("Loaded %d stars from SIMBAD cache.", len(stars))
        return stars


# ---------------------------------------------------------------------------
# Local catalog adapter
# ---------------------------------------------------------------------------


class LocalCatalogAdapter:
    """
    Load a star catalog from a user-supplied CSV or FITS file.

    Expected CSV columns (case-insensitive):
      Required: ra_deg OR ra, dec_deg OR dec OR de  AND  vmag OR v_mag OR vmag
      Optional: star_id, star_name OR name, spectral_type OR sptype
    """

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def load(self) -> List[StarCandidate]:
        """Load and return stars from the local file."""
        suffix = self.file_path.suffix.lower()
        if suffix == ".csv":
            return self._load_csv()
        elif suffix in {".fits", ".fit", ".fz"}:
            return self._load_fits()
        else:
            raise ValueError(
                f"Unsupported file type {suffix!r}. Use .csv or .fits."
            )

    # ------------------------------------------------------------------
    def _load_csv(self) -> List[StarCandidate]:
        df = pd.read_csv(self.file_path, dtype=str, na_filter=False)
        df.columns = [c.lower().strip() for c in df.columns]
        return self._dataframe_to_stars(df)

    def _load_fits(self) -> List[StarCandidate]:
        from astropy.table import Table
        tbl = Table.read(str(self.file_path))
        df = tbl.to_pandas()
        df.columns = [c.lower().strip() for c in df.columns]
        return self._dataframe_to_stars(df)

    def _dataframe_to_stars(self, df: pd.DataFrame) -> List[StarCandidate]:
        """Convert a normalised DataFrame to StarCandidate list."""
        # Column alias resolution
        col_ra = _first_col(df, ["ra_deg", "ra", "raj2000"])
        col_dec = _first_col(df, ["dec_deg", "de", "dec", "dej2000"])
        col_vmag = _first_col(df, ["vmag", "v_mag", "v"])
        col_id = _first_col(df, ["star_id", "id", "hip", "hd"])
        col_name = _first_col(df, ["star_name", "name", "designation"])
        col_sp = _first_col(df, ["spectral_type", "sptype", "sp"])

        if col_ra is None or col_dec is None or col_vmag is None:
            missing = [n for n, c in [("ra_deg", col_ra), ("dec_deg", col_dec), ("vmag", col_vmag)] if c is None]
            raise ValueError(
                f"Local catalog file is missing required columns: {missing}. "
                "Expected: ra_deg (or ra/raj2000), dec_deg (or dec/dej2000), vmag (or v_mag/v)."
            )

        stars: List[StarCandidate] = []
        for i, row in df.iterrows():
            try:
                ra = float(row[col_ra])
                dec = float(row[col_dec])
                vmag = float(row[col_vmag])
            except (ValueError, TypeError):
                continue

            star_id = str(row[col_id]) if col_id else f"LOCAL_{i}"
            star_name = str(row[col_name]) if col_name else star_id
            sptype = str(row[col_sp]) if col_sp else ""

            stars.append(
                StarCandidate(
                    star_id=star_id,
                    star_name=star_name,
                    ra_deg=ra,
                    dec_deg=dec,
                    vmag=vmag,
                    catalog_source=f"local:{self.file_path.name}",
                    spectral_type=sptype[:10] if sptype else "",
                )
            )

        log.info("Loaded %d stars from local catalog: %s", len(stars), self.file_path)
        return stars


# ---------------------------------------------------------------------------
# Unified catalog loader
# ---------------------------------------------------------------------------


def load_catalog(
    source: str,
    vmag_limit: float = 7.5,
    local_path: str = "",
    force_refresh: bool = False,
) -> List[StarCandidate]:
    """Unified entry point for all catalog sources.

    Parameters
    ----------
    source : "vizier" | "simbad" | "local"
    vmag_limit : maximum V magnitude to load (ignored for local catalogs).
    local_path : path to local file (required when source="local").
    force_refresh : force re-download even if a cache exists.

    Returns
    -------
    list of StarCandidate with multi-band photometry where available.
    """
    if source == "vizier":
        adapter = VizierCatalogAdapter(vmag_limit=vmag_limit)
        return adapter.load(force_refresh=force_refresh)
    elif source == "simbad":
        adapter = SimbadCatalogAdapter(vmag_limit=vmag_limit)
        return adapter.load(force_refresh=force_refresh)
    elif source == "local":
        if not local_path:
            raise ValueError("local_path must be set when catalog_source='local'.")
        adapter = LocalCatalogAdapter(file_path=local_path)
        return adapter.load()
    else:
        raise ValueError(
            f"Unknown catalog source: {source!r}. Use 'vizier', 'simbad', or 'local'."
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _first_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first column name from *candidates* that exists in *df*."""
    for c in candidates:
        if c in df.columns:
            return c
    return None
