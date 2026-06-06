"""Equivalence tests: the MCP output == the data galah returns.

Two levels:

1. OFFLINE (default, no network): a fake galah is injected with reference
   DataFrames and we check that each tool returns EXACTLY the same records as that
   DataFrame, without altering them. This verifies the MCP layer is transparent
   with respect to galah's data.

2. LIVE (opt-in via GALAH_LIVE=1 and GALAH_EMAIL): the real API is called and we
   check galah's internal consistency through the wrapper (e.g. atlas_counts
   matches the number of rows from atlas_occurrences), and that the tool returns
   the same thing as a direct call to galah.
"""

from __future__ import annotations

import json
import os

import pandas as pd
import pytest

import server


def records_of(df: pd.DataFrame) -> list[dict]:
    """Reference conversion, independent of the wrapper's own.

    Defines what "equivalent" means: the same records as the source DataFrame.
    """
    return json.loads(df.to_json(orient="records", date_format="iso"))


# --------------------------------------------------------------------------- #
# 1. Offline equivalence (transparent wrapper)
# --------------------------------------------------------------------------- #
class TestWrapperEquivalence:
    def test_search_taxa(self, fake_galah):
        out = server.search_taxa("Vulpes vulpes")
        assert out["matches"] == records_of(fake_galah.frames["search_taxa"])
        # and it forwards the parameter as-is
        assert fake_galah.calls["search_taxa"]["taxa"] == "Vulpes vulpes"

    def test_atlas_counts(self, fake_galah):
        out = server.atlas_counts(taxa="Vulpes vulpes", filters=["year=2023"], group_by="year")
        assert out["counts"] == records_of(fake_galah.frames["atlas_counts"])
        c = fake_galah.calls["atlas_counts"]
        assert c["taxa"] == "Vulpes vulpes"
        assert c["filters"] == ["year=2023"]
        assert c["group_by"] == "year"

    def test_atlas_species(self, fake_galah):
        out = server.atlas_species(taxa="Heleioporus")
        assert out["species"] == records_of(fake_galah.frames["atlas_species"])
        assert out["row_count"] == len(fake_galah.frames["atlas_species"])

    def test_search_fields(self, fake_galah):
        out = server.search_fields("year")
        assert out["fields"] == records_of(fake_galah.frames["search_all"])

    def test_show_field_values(self, fake_galah):
        out = server.show_field_values("basisOfRecord")
        assert out["values"] == records_of(fake_galah.frames["show_values"])

    def test_list_atlases(self, fake_galah):
        out = server.list_atlases()
        assert out["atlases"] == records_of(fake_galah.frames["show_all"])

    def test_set_config(self, fake_galah):
        out = server.set_config(email="test@example.com", atlas="Australia", reason=4)
        assert out["config"] == records_of(fake_galah.frames["galah_config"])
        # the wrapper forwards the parameters to galah_config (it also calls it a
        # second time with no args to read the config back, hence the history check)
        assert ("galah_config", {
            "email": "test@example.com",
            "atlas": "Australia",
            "reason": 4,
        }) in fake_galah.history


# --------------------------------------------------------------------------- #
# 2. Download equivalence (inline sample vs full CSV)
# --------------------------------------------------------------------------- #
class TestOccurrencesEquivalence:
    def test_small_download_inline(self, fake_galah):
        """<= limit: records are returned inline, identical to the DataFrame."""
        df = pd.DataFrame([{"a": i, "scientificName": "X"} for i in range(5)])
        fake_galah._occurrences_frame = df

        out = server.atlas_occurrences("X")
        assert out["row_count"] == 5
        assert "csv_path" not in out
        assert out["records"] == records_of(df)

    def test_large_download_csv_equivalent(self, fake_galah, tmp_path):
        """> limit: the sample is the first N rows and the CSV reconstructs the original."""
        n = server.INLINE_ROW_LIMIT + 25
        df = pd.DataFrame([{"a": i, "scientificName": "X"} for i in range(n)])
        fake_galah._occurrences_frame = df

        out = server.atlas_occurrences("X")
        assert out["row_count"] == n
        # sample = first INLINE_ROW_LIMIT rows, unaltered
        assert out["sample"] == records_of(df.head(server.INLINE_ROW_LIMIT))
        # the saved CSV reconstructs the original DataFrame exactly
        reloaded = pd.read_csv(out["csv_path"])
        pd.testing.assert_frame_equal(reloaded, df)

    def test_force_save_csv(self, fake_galah):
        """save_csv=True saves even when the dataset is small."""
        df = pd.DataFrame([{"a": 1, "scientificName": "X"}])
        fake_galah._occurrences_frame = df
        out = server.atlas_occurrences("X", save_csv=True)
        assert "csv_path" in out
        assert out["sample"] == records_of(df)


# --------------------------------------------------------------------------- #
# 3. Live equivalence against the real API (opt-in)
# --------------------------------------------------------------------------- #
LIVE = os.environ.get("GALAH_LIVE") == "1"
live = pytest.mark.skipif(not LIVE, reason="Set GALAH_LIVE=1 (and GALAH_EMAIL) for live tests")


@live
class TestLiveEquivalence:
    @pytest.fixture(autouse=True)
    def _config(self):
        import galah

        galah.galah_config(
            email=os.environ.get("GALAH_EMAIL", ""),
            atlas=os.environ.get("GALAH_ATLAS", "Australia"),
        )

    def test_tool_matches_direct_call(self):
        """search_taxa via MCP == direct galah.search_taxa call."""
        import galah

        direct = galah.search_taxa(taxa="Vulpes vulpes")
        via_tool = server.search_taxa("Vulpes vulpes")["matches"]
        assert via_tool == records_of(direct)

    def test_counts_match_occurrences_rows(self):
        """Internal consistency: atlas_counts ~= number of occurrences for a small query."""
        taxa = "Heleioporus eyrei"
        filters = ["year=2020"]
        total = server.atlas_counts(taxa=taxa, filters=filters)["counts"][0]
        total = total.get("totalRecords", total.get("count"))

        occ = server.atlas_occurrences(taxa=taxa, filters=filters, save_csv=True)
        assert occ["row_count"] == total
