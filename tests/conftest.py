"""Shared pytest compatibility helpers."""

from sqlalchemy.pool import QueuePool


if not hasattr(QueuePool, "_use_lifo"):
    QueuePool._use_lifo = property(lambda pool: pool._pool.use_lifo)
