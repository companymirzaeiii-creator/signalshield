"""FalkorDB access isolated to SignalShield's graph and port."""

from functools import lru_cache
from time import sleep

from falkordb import FalkorDB

GRAPH_NAME = "signalshield"


@lru_cache(maxsize=1)
def get_graph():
    return FalkorDB(host="localhost", port=6380).select_graph(GRAPH_NAME)


def rows(query: str, params: dict | None = None):
    last_error = None
    for attempt in range(2):
        try:
            return get_graph().ro_query(query, params=params, timeout=5).result_set
        except Exception as error:
            last_error = error
            get_graph.cache_clear()
            if attempt == 0:
                sleep(0.2)
    raise RuntimeError("SignalShield cannot reach FalkorDB. Run `docker compose up -d` in this folder.") from last_error
