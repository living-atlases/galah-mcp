"""Shared fixtures for galah-mcp tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd
import pytest

# Allow importing `server.py` (which lives at the project root, not in tests/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeGalah(types.SimpleNamespace):
    """Test double for the galah library.

    Each function returns a fixed DataFrame and records the arguments it was called
    with, so we can check (a) that the wrapper forwards the right parameters and
    (b) that the tool output is equivalent to that same DataFrame.
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls: dict[str, dict] = {}          # last kwargs per function
        self.history: list[tuple[str, dict]] = []  # full call history (name, kwargs)
        # Reference DataFrames, one per function.
        self.frames = {
            "galah_config": pd.DataFrame([{"email": "test@example.com", "atlas": "Australia"}]),
            "search_taxa": pd.DataFrame(
                [{"scientificName": "Vulpes vulpes", "rank": "species", "vernacularName": "Fox"}]
            ),
            "atlas_counts": pd.DataFrame([{"year": 2023, "count": 8516}]),
            "atlas_species": pd.DataFrame(
                [{"Species Name": "Heleioporus eyrei", "Genus": "Heleioporus"}]
            ),
            "search_all": pd.DataFrame([{"id": "year", "description": "Year of record"}]),
            "show_values": pd.DataFrame(
                [{"field": "basisOfRecord", "category": "HUMAN_OBSERVATION"}]
            ),
            "show_all": pd.DataFrame([{"atlas": "Australia"}, {"atlas": "GBIF"}]),
        }

    def _record(self, name, kwargs):
        self.calls[name] = kwargs
        self.history.append((name, kwargs))

    def galah_config(self, **kwargs):
        self._record("galah_config", kwargs)
        return self.frames["galah_config"]

    def search_taxa(self, **kwargs):
        self._record("search_taxa", kwargs)
        return self.frames["search_taxa"]

    def atlas_counts(self, **kwargs):
        self._record("atlas_counts", kwargs)
        return self.frames["atlas_counts"]

    def atlas_species(self, **kwargs):
        self._record("atlas_species", kwargs)
        return self.frames["atlas_species"]

    def search_all(self, **kwargs):
        self._record("search_all", kwargs)
        return self.frames["search_all"]

    def show_values(self, **kwargs):
        self._record("show_values", kwargs)
        return self.frames["show_values"]

    def show_all(self, **kwargs):
        self._record("show_all", kwargs)
        return self.frames["show_all"]

    # atlas_occurrences is set per test (its size varies by case).
    def atlas_occurrences(self, **kwargs):
        self._record("atlas_occurrences", kwargs)
        return self._occurrences_frame

    _occurrences_frame = pd.DataFrame(
        [{"decimalLatitude": -39.08, "scientificName": "Vulpes vulpes"}]
    )


@pytest.fixture
def fake_galah(monkeypatch, tmp_path):
    """Inject a fake galah into the `server` module and isolate the download dir."""
    import server

    fake = FakeGalah()
    monkeypatch.setattr(server, "galah", fake)
    monkeypatch.setattr(server, "DOWNLOAD_DIR", tmp_path)
    return fake
