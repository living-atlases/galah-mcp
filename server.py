"""
galah-mcp — An MCP server exposing the `galah` library (Atlas of Living Australia)
as tools for LLM assistants.

It wraps galah-python (https://galah.ala.org.au/Python/) with the official MCP SDK
(FastMCP). Intended as a working v1 skeleton: taxon search, counts, occurrence
downloads, species lists, and field exploration.

Proof of concept — experimental, not affiliated with or endorsed by the Atlas of
Living Australia or GBIF. Not production-ready; expect breaking changes.

Design principles:
- Tools return MANAGEABLE data (counts, samples, or file paths), never raw datasets
  of thousands of rows dumped into the model context.
- Configuration (email + atlas) is done with a dedicated tool, because ALA requires
  a registered email to download occurrences.
- Each tool converts galah's pandas.DataFrame into something serializable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import galah
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("galah")

# Directory where large downloads are stored (configurable via env var).
DOWNLOAD_DIR = Path(os.environ.get("GALAH_DOWNLOAD_DIR", "./galah_downloads")).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Threshold above which a download is saved to disk instead of returned inline.
INLINE_ROW_LIMIT = 50


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _df_to_records(df, limit: Optional[int] = None) -> list[dict]:
    """Convert a pandas DataFrame into a JSON-serializable list of dicts."""
    if df is None:
        return []
    if limit is not None:
        df = df.head(limit)
    # to_json -> avoids issues with NaN, dates, numpy types, etc.
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _configure_from_env() -> None:
    """Apply email/atlas from environment variables at startup, if present."""
    email = os.environ.get("GALAH_EMAIL")
    atlas = os.environ.get("GALAH_ATLAS", "Australia")
    reason = os.environ.get("GALAH_REASON")
    kwargs = {"atlas": atlas}
    if email:
        kwargs["email"] = email
    if reason:
        kwargs["reason"] = int(reason)
    galah.galah_config(**kwargs)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def set_config(
    email: Optional[str] = None,
    atlas: Optional[str] = None,
    reason: Optional[int] = None,
) -> dict:
    """Configure galah. Required before downloading occurrences.

    Args:
        email: An email address that has been registered with the chosen atlas.
               For the ALA, you can register at
               https://auth.ala.org.au/userdetails/registration/createAccount
               (required for atlas_occurrences).
        atlas: Atlas to use ("Australia", "GBIF", "Austria", etc.). See list_atlases().
        reason: Download reason (integer). 4 = scientific research (default).

    Returns:
        The current galah configuration.
    """
    kwargs = {}
    if email is not None:
        kwargs["email"] = email
    if atlas is not None:
        kwargs["atlas"] = atlas
    if reason is not None:
        kwargs["reason"] = reason
    if kwargs:
        galah.galah_config(**kwargs)
    # With no arguments, galah_config() returns a DataFrame with the current config.
    current = galah.galah_config()
    return {"config": _df_to_records(current)}


@mcp.tool()
def search_taxa(taxa: str) -> dict:
    """Search a scientific name and return its taxonomic identifier and classification.

    This is the first step before counting or downloading: it resolves common/scientific
    names to valid taxa and disambiguates homonyms.

    Args:
        taxa: Scientific or common name to search (e.g. "Vulpes vulpes", "Ornithorhynchus anatinus").

    Returns:
        Matching rows with scientificName, taxonConceptID, rank, classification and vernacularName.
    """
    df = galah.search_taxa(taxa=taxa)
    return {"matches": _df_to_records(df)}


@mcp.tool()
def atlas_counts(
    taxa: Optional[str] = None,
    filters: Optional[list[str]] = None,
    group_by: Optional[str] = None,
) -> dict:
    """Count how many occurrence records match the criteria. Fast and cheap.

    ALWAYS use this before atlas_occurrences to estimate the size of a download.

    Args:
        taxa: Scientific name (e.g. "Vulpes vulpes"). Optional.
        filters: List of "field logical value" filters (e.g. ["year=2023", "decimalLongitude>153.0"]).
        group_by: Field to group counts by (e.g. "year", "stateProvince").

    Returns:
        A total record count, or a table of counts per group.
    """
    df = galah.atlas_counts(taxa=taxa, filters=filters, group_by=group_by)
    return {"counts": _df_to_records(df)}


@mcp.tool()
def atlas_occurrences(
    taxa: str,
    filters: Optional[list[str]] = None,
    fields: Optional[str] = None,
    max_inline_rows: int = INLINE_ROW_LIMIT,
    save_csv: bool = False,
) -> dict:
    """Download occurrence records. REQUIRES a configured email (set_config).

    For large downloads, returns only a sample and saves the full dataset to CSV.
    Call atlas_counts() first to know how many records to expect.

    Args:
        taxa: Scientific name (e.g. "Vulpes vulpes").
        filters: List of "field logical value" filters (e.g. ["year=2023"]).
        fields: Field group to include ("basic", "event", "media", "assertions") or specific fields.
        max_inline_rows: Maximum number of rows to return inline. The rest is summarized.
        save_csv: If True, always save the full dataset to CSV and return its path.

    Returns:
        Row count, a sample of the records and (if applicable) the path to the full CSV.
    """
    df = galah.atlas_occurrences(taxa=taxa, filters=filters, fields=fields)
    if df is None:
        return {"row_count": 0, "columns": [], "records": []}
    n = len(df)

    result: dict = {"row_count": n, "columns": list(df.columns) if n else []}

    if save_csv or n > max_inline_rows:
        safe = "".join(c if c.isalnum() else "_" for c in taxa)[:40]
        path = DOWNLOAD_DIR / f"occurrences_{safe}_{n}rows.csv"
        df.to_csv(path, index=False)
        result["csv_path"] = str(path)
        result["sample"] = _df_to_records(df, limit=max_inline_rows)
        result["note"] = (
            f"Returned {min(n, max_inline_rows)} of {n} rows. "
            f"Full dataset saved to {path}."
        )
    else:
        result["records"] = _df_to_records(df)
    return result


@mcp.tool()
def atlas_species(
    taxa: str,
    filters: Optional[list[str]] = None,
    rank: str = "species",
) -> dict:
    """List the species occurring in a taxonomic group / region / time period.

    One row per species, with its taxonomic information. Lighter than atlas_occurrences
    when you only want to know WHICH species are present, not every record.

    Args:
        taxa: Scientific name of the group (e.g. "Heleioporus", "Aves").
        filters: List of "field logical value" filters.
        rank: Rank to return ("species", "genus", ...). Defaults to "species".

    Returns:
        A table with one species per row.
    """
    df = galah.atlas_species(taxa=taxa, filters=filters, rank=rank)
    return {"row_count": 0 if df is None else len(df), "species": _df_to_records(df)}


@mcp.tool()
def search_fields(query: str) -> dict:
    """Search available fields in the atlas to use in `filters`.

    Useful for discovering valid field names before building filters.

    Args:
        query: Text to search across fields (e.g. "year", "state", "basis").

    Returns:
        Matching fields with their id and description.
    """
    df = galah.search_all(fields=query)
    return {"fields": _df_to_records(df, limit=100)}


@mcp.tool()
def show_field_values(field: str) -> dict:
    """Show the valid categorical values of a given field.

    Args:
        field: Field name (e.g. "basisOfRecord", "stateProvince").

    Returns:
        The admissible values for that field.
    """
    df = galah.show_values(field=field)
    return {"values": _df_to_records(df, limit=200)}


@mcp.tool()
def list_atlases() -> dict:
    """List the available atlases (ALA, GBIF, and national nodes) for set_config."""
    df = galah.show_all(atlases=True)
    return {"atlases": _df_to_records(df)}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    try:
        _configure_from_env()
    except Exception as exc:  # noqa: BLE001 - a config failure must not take the server down
        print(f"[galah-mcp] Warning: could not apply config from environment: {exc}")
    mcp.run()


if __name__ == "__main__":
    main()
