from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from utils.jobs import IndexJobs


@pytest.mark.asyncio
async def test_jobs_duplicate_and_failure():
    jobs = IndexJobs()
    job = jobs.submit(1)
    with pytest.raises(ValueError):
        jobs.submit(1)
    await jobs.run(job["job_id"], AsyncMock(side_effect=RuntimeError("offline")))
    assert job["state"] == "failed"
    next_job = jobs.submit(1)
    await jobs.run(
        next_job["job_id"], AsyncMock(return_value=SimpleNamespace(status_code=200))
    )
    assert next_job["state"] == "succeeded"


def test_queue_bound():
    jobs = IndexJobs()
    for i in range(8):
        jobs.submit(i)
    with pytest.raises(ValueError):
        jobs.submit(9)
