"""CI sanity check: configs parse and module contracts import cleanly."""

from __future__ import annotations

from scripts.config_loader import all_entity_aliases, load_taxonomy, load_watchlist

# Importing the data contracts also proves they are syntactically valid.
from scripts.interfaces import Candidate, Incident, RawItem  # noqa: F401


def main() -> None:
    taxonomy = load_taxonomy()
    watchlist = load_watchlist()

    assert "definition" in taxonomy, "taxonomy missing definition"
    for layer in ("event", "mechanism", "consequence"):
        assert layer in taxonomy, f"taxonomy missing layer: {layer}"
    assert "views" in taxonomy, "taxonomy missing views"

    entities = all_entity_aliases(watchlist)
    assert entities, "watchlist produced no entities"

    print(f"OK: taxonomy valid, {len(entities)} watchlist entities loaded")


if __name__ == "__main__":
    main()
