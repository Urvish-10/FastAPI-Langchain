import asyncio
import threading
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    ChannelVersions,
    get_checkpoint_metadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection, Connection
from psycopg.errors import UndefinedTable
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import settings

UPSERT_CHECKPOINTS_SQL = """
    INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata, user_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id)
    DO UPDATE SET
        checkpoint = EXCLUDED.checkpoint,
        metadata = EXCLUDED.metadata;
"""

SELECT_THREAD_LIST = """
    SELECT thread_id, metadata FROM public.checkpoints WHERE user_id = '{}' and metadata ->> 'step' = '-1' ORDER BY checkpoint_id DESC;
"""

SELECT_THREAD_MESSAGES = """
                         SELECT *
                         FROM public.checkpoints
                         WHERE thread_id = '{}'
                           AND user_id = '{}'
                         ORDER BY checkpoint_id; \
                         """


class CustomAsyncPostgresSaver(AsyncPostgresSaver):
    lock: asyncio.Lock
    UPSERT_CHECKPOINTS_SQL = UPSERT_CHECKPOINTS_SQL
    MIGRATIONS = AsyncPostgresSaver.MIGRATIONS + [
        "ALTER TABLE checkpoints ADD user_id TEXT DEFAULT NULL;",
    ]

    @classmethod
    @asynccontextmanager
    async def from_conn_string(
        cls,
        # conn_string: str,
        *,
        pipeline: bool = False,
        serde=None,
    ) -> AsyncIterator["CustomAsyncPostgresSaver"]:
        """Create a new PostgresSaver instance from a connection string.

        Args:
            conn_string (str): The Postgres connection info string.
            pipeline (bool): whether to use AsyncPipeline

        Returns:
            CustomAsyncPostgresSaver: A new CustomAsyncPostgresSaver instance.
        """
        conn_string = str(settings.SQLALCHEMY_DATABASE_URI).replace(
            "postgresql+psycopg://", "postgresql://"
        )
        async with await AsyncConnection.connect(
            conn_string, autocommit=True, prepare_threshold=0, row_factory=dict_row
        ) as conn:
            if pipeline:
                async with conn.pipeline() as pipe:
                    yield CustomAsyncPostgresSaver(conn=conn, pipe=pipe, serde=serde)
            else:
                yield CustomAsyncPostgresSaver(conn=conn, serde=serde)

    async def setup(self) -> None:
        """Set up the checkpoint database asynchronously.

        This method creates the necessary tables in the Postgres database if they don't
        already exist and runs database migrations. It MUST be called directly by the user
        the first time checkpointer is used.
        """
        async with self._cursor() as cur:
            try:
                await cur.execute(self.MIGRATIONS[0])
                results = await cur.execute(
                    "SELECT v FROM checkpoint_migrations ORDER BY v DESC LIMIT 1"
                )
                row = await results.fetchone()
                if row is None:
                    version = -1
                else:
                    version = row["v"]
            except UndefinedTable:
                version = -1
            for v, migration in zip(
                range(version + 1, len(self.MIGRATIONS)),
                self.MIGRATIONS[version + 1 :],
            ):
                await cur.execute(migration)
                await cur.execute(f"INSERT INTO checkpoint_migrations (v) VALUES ({v})")
        if self.pipe:
            await self.pipe.sync()

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database asynchronously.

        This method saves a checkpoint to the Postgres database. The checkpoint is associated
        with the provided config and its parent config (if any).

        Args:
            config (RunnableConfig): The config to associate with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to save.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """

        configurable = config["configurable"].copy()
        thread_id = configurable.pop("thread_id")
        checkpoint_ns = configurable.pop("checkpoint_ns")
        checkpoint_id = configurable.pop(
            "checkpoint_id", configurable.pop("thread_ts", None)
        )

        copy = checkpoint.copy()
        copy["channel_values"] = copy["channel_values"].copy()
        next_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

        # inline primitive values in checkpoint table
        # others are stored in blobs table
        blob_values = {}
        for k, v in checkpoint["channel_values"].items():
            if v is None or isinstance(v, (str, int, float, bool)):
                pass
            else:
                blob_values[k] = copy["channel_values"].pop(k)

        async with self._cursor(pipeline=True) as cur:
            if blob_versions := {
                k: v for k, v in new_versions.items() if k in blob_values
            }:
                await cur.executemany(
                    self.UPSERT_CHECKPOINT_BLOBS_SQL,
                    await asyncio.to_thread(
                        self._dump_blobs,
                        thread_id,
                        checkpoint_ns,
                        blob_values,
                        blob_versions,
                    ),
                )
            await cur.execute(
                self.UPSERT_CHECKPOINTS_SQL,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint["id"],
                    checkpoint_id,
                    Jsonb(copy),
                    Jsonb(get_checkpoint_metadata(config, metadata)),
                    configurable.get("user_id"),
                ),
            )
        return next_config


class CustomSyncPostgresSaver(PostgresSaver):
    lock: threading.Lock
    UPSERT_CHECKPOINTS_SQL = UPSERT_CHECKPOINTS_SQL
    MIGRATIONS = PostgresSaver.MIGRATIONS + [
        "ALTER TABLE checkpoints ADD user_id TEXT DEFAULT NULL;",
    ]

    @classmethod
    @contextmanager
    def from_conn_string(
        cls,
        # conn_string: str,
        *,
        pipeline: bool = False,
    ) -> Iterator["CustomSyncPostgresSaver"]:
        """Create a new PostgresSaver instance from a connection string.

        Args:
            conn_string (str): The Postgres connection info string.
            pipeline (bool): whether to use Pipeline

        Returns:
            PostgresSaver: A new PostgresSaver instance.
        """
        conn_string = str(settings.SQLALCHEMY_DATABASE_URI).replace(
            "postgresql+psycopg://", "postgresql://"
        )
        with Connection.connect(
            conn_string, autocommit=True, prepare_threshold=0, row_factory=dict_row
        ) as conn:
            if pipeline:
                with conn.pipeline() as pipe:
                    yield CustomSyncPostgresSaver(conn, pipe)
            else:
                yield CustomSyncPostgresSaver(conn)

    def user_list(
        self,
        config: RunnableConfig | None,
        user_id: str,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints from the database.

        This method retrieves a list of checkpoint tuples from the Postgres database based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

        Args:
            config: The config to use for listing the checkpoints.
            filter: Additional filtering criteria for metadata. Defaults to None.
            before: If provided, only checkpoints before the specified checkpoint ID are returned. Defaults to None.
            limit: The maximum number of checkpoints to return. Defaults to None.

        Yields:
            Iterator[CheckpointTuple]: An iterator of checkpoint tuples.

        Examples:
            >>> from langgraph.checkpoint.postgres import PostgresSaver
            >>> DB_URI = "postgres://postgres:postgres@localhost:5432/postgres?sslmode=disable"
            >>> with PostgresSaver.from_conn_string(DB_URI) as memory:
            ... # Run a graph, then list the checkpoints
            >>>     config = {"configurable": {"thread_id": "1"}}
            >>>     checkpoints = list(memory.list(config, limit=2))
            >>> print(checkpoints)
            [CheckpointTuple(...), CheckpointTuple(...)]

            >>> config = {"configurable": {"thread_id": "1"}}
            >>> before = {"configurable": {"checkpoint_id": "1ef4f797-8335-6428-8001-8a1503f9b875"}}
            >>> with PostgresSaver.from_conn_string(DB_URI) as memory:
            ... # Run a graph, then list the checkpoints
            >>>     checkpoints = list(memory.list(config, before=before))
            >>> print(checkpoints)
            [CheckpointTuple(...), ...]
        """
        where, args = self._search_where(config, filter, before)
        if where:
            where = where + f" and user_id='{user_id}'"
        else:
            where = f" where user_id='{user_id}'"
        query = self.SELECT_SQL + where + " ORDER BY checkpoint_id DESC"
        if limit:
            query += f" LIMIT {limit}"
        # if we change this to use .stream() we need to make sure to close the cursor
        with self._cursor() as cur:
            cur.execute(query, args)
            values = cur.fetchall()
            if not values:
                return
            # migrate pending sends if necessary
            if to_migrate := [
                v
                for v in values
                if v["checkpoint"]["v"] < 4 and v["parent_checkpoint_id"]
            ]:
                cur.execute(
                    self.SELECT_PENDING_SENDS_SQL,
                    (
                        values[0]["thread_id"],
                        [v["parent_checkpoint_id"] for v in to_migrate],
                    ),
                )
                grouped_by_parent = defaultdict(list)
                for value in to_migrate:
                    grouped_by_parent[value["parent_checkpoint_id"]].append(value)
                for sends in cur:
                    for value in grouped_by_parent[sends["checkpoint_id"]]:
                        if value["channel_values"] is None:
                            value["channel_values"] = []
                        self._migrate_pending_sends(
                            sends["sends"],
                            value["checkpoint"],
                            value["channel_values"],
                        )
            for value in values:
                yield self._load_checkpoint_tuple(value)

    def get_thread_data(
        self, config: RunnableConfig, user_id: str
    ) -> CheckpointTuple | None:
        """Get a checkpoint tuple from the database.

        This method retrieves a checkpoint tuple from the Postgres database based on the
        provided config. If the config contains a "checkpoint_id" key, the checkpoint with
        the matching thread ID and timestamp is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config: The config to use for retrieving the checkpoint.

        Returns:
            Optional[CheckpointTuple]: The retrieved checkpoint tuple, or None if no matching checkpoint was found.

        Examples:

            Basic:
            >>> config = {"configurable": {"thread_id": "1"}}
            >>> checkpoint_tuple = memory.get_tuple(config)
            >>> print(checkpoint_tuple)
            CheckpointTuple(...)

            With timestamp:

            >>> config = {
            ...    "configurable": {
            ...        "thread_id": "1",
            ...        "checkpoint_ns": "",
            ...        "checkpoint_id": "1ef4f797-8335-6428-8001-8a1503f9b875",
            ...    }
            ... }
            >>> checkpoint_tuple = memory.get_tuple(config)
            >>> print(checkpoint_tuple)
            CheckpointTuple(...)
        """  # noqa
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        # if checkpoint_id:
        #     args: tuple[Any, ...] = (thread_id, checkpoint_ns, checkpoint_id)
        #     where = "WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s"
        # else:
        args = (thread_id, checkpoint_ns)
        where = f"WHERE thread_id = %s AND checkpoint_ns = %s AND user_id='{user_id}' ORDER BY checkpoint_id DESC LIMIT 1"
        with self._cursor() as cur:
            cur.execute(
                self.SELECT_SQL + where,
                args,
            )
            value = cur.fetchone()
            if value is None:
                return None

            # migrate pending sends if necessary
            if value["checkpoint"]["v"] < 4 and value["parent_checkpoint_id"]:
                cur.execute(
                    self.SELECT_PENDING_SENDS_SQL,
                    (thread_id, [value["parent_checkpoint_id"]]),
                )
                if sends := cur.fetchone():
                    if value["channel_values"] is None:
                        value["channel_values"] = []
                    self._migrate_pending_sends(
                        sends["sends"],
                        value["checkpoint"],
                        value["channel_values"],
                    )

            return self._load_checkpoint_tuple(value)
