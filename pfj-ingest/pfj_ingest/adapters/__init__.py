"""Source adapters.

Each adapter is a function taking a source config dict and returning a
list of Event objects. Register it below; the runner dispatches on the
"adapter" key in config/sources.json.
"""

from . import agile, ics, jsonld, manual, tribe, veezi

REGISTRY = {
    "manual": manual.pull,
    "veezi": veezi.pull,
    "agile": agile.pull,
    "ics": ics.pull,
    "tribe": tribe.pull,
    "jsonld": jsonld.pull,
}


def get(name: str):
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown adapter '{name}'. Known adapters: {', '.join(sorted(REGISTRY))}"
        ) from None
