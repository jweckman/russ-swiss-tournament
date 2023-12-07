import os
from datetime import datetime, timedelta

from sqlmodel import Session, select, SQLModel, create_engine

# Proper Prod way
# DATABASE_URL = os.environ["DATABASE_URL"]

# Local testing way
sqlite_file_name = "database.db"
DATABASE_URL = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def populate_test_data():
    pass
