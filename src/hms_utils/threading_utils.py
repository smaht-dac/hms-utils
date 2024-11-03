import concurrent.futures
from typing import Callable, Iterable


def run_concurrently(functions: Iterable[Callable], nthreads: int = 4) -> None:
    # FYI: Not pulling in from dcicutils.misc_utils becausethere is
    # a call to logging.basicConfig() which is (for some reason) causing
    # exceptions within the asynchronous function calls to be output.
    if not (isinstance(nthreads, int) and (nthreads > 0)):
        nthreads = 4
    with concurrent.futures.ThreadPoolExecutor(max_workers=nthreads) as executor:
        concurrent.futures.as_completed([executor.submit(f) for f in functions])
