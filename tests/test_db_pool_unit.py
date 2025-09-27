import asyncio

from app.db import pool as dbpool


def test_check_ready_false_when_uninitialized():
    # Ensure pool is closed/None
    asyncio.run(dbpool.close_pool())
    assert asyncio.run(dbpool.check_ready()) is False
