import json
import pandas as pd
import polars as pl
from pymongo import MongoClient


def mongodb_connector(host, database, user, password, port, collection, query=None, connection_string=None, limit=None):
    """Read documents from a MongoDB collection and return them as a Polars DataFrame.

    MongoDB has no SQL query language, so unlike the SQL connectors this
    takes a `collection` name plus an optional `query`, which is a JSON
    string representing a Mongo filter document (e.g. '{"status": "active"}').
    An empty/None query matches all documents.

    If `connection_string` is provided (a full mongodb:// or mongodb+srv://
    URI), it is used as-is and host/port/user/password are ignored — this is
    the common way to connect to MongoDB Atlas.
    """
    try:
        if connection_string:
            client = MongoClient(connection_string, serverSelectionTimeoutMS=8000)
        else:
            client = MongoClient(
                host=host,
                port=int(port) if port else 27017,
                username=user or None,
                password=password or None,
                serverSelectionTimeoutMS=8000,
            )

        db = client[database]
        coll = db[collection]

        mongo_filter = {}
        if query and str(query).strip():
            mongo_filter = json.loads(query)

        cursor = coll.find(mongo_filter)
        if limit:
            cursor = cursor.limit(int(limit))

        docs = list(cursor)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])

        print(f"Connected to: {host or connection_string}/{database}.{collection}")
        df = pd.DataFrame(docs)
        print(f"Query executed — {df.shape[0]} rows fetched")

        client.close()
        return pl.from_pandas(df) if not df.empty else pl.DataFrame(docs)

    except json.JSONDecodeError as e:
        raise Exception(f"MongoDB query filter is not valid JSON: {e}")
    except Exception as e:
        raise Exception(f"MongoDB connection failed: {e}")
