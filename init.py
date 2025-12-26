from app.models.users.user import Users

from sqlmodel import SQLModel
from sqlmodel import create_engine

from app.agent_utils.postgres_saver import CustomSyncPostgresSaver
from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db():
    # This function is used to create SQL Models into Database, if not Alembic then only use this way, simpler for demo purpose.
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    # init_db()
    # The below connection is used to create tables for langgraph checkpoints and memory
    with CustomSyncPostgresSaver.from_conn_string() as checkpointer:
        checkpointer.setup()
    print('------ Setup complete ------')
