"""
Writes rows OUT to a MongoDB collection. Config keys match
testers/mongodb.py exactly, so an existing MongoDB saved connection can be
reused as a reverse-ETL destination unchanged.

config keys: connection_string (mongodb:// / mongodb+srv://, takes priority)
             OR host, port (default 27017), user, password
             database (required)
"""

try:
    from pymongo import MongoClient, UpdateOne
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


def _connect(config: dict) -> "MongoClient":
    if not PYMONGO_AVAILABLE:
        raise ImportError("MongoDB support requires pymongo (pip install pymongo).")
    connection_string = config.get("connection_string")
    if connection_string:
        return MongoClient(connection_string, serverSelectionTimeoutMS=10000)
    return MongoClient(
        host=config.get("host"),
        port=int(config.get("port") or 27017),
        username=config.get("user") or None,
        password=config.get("password") or None,
        serverSelectionTimeoutMS=10000,
    )


def mongodb_writer(records: list, config: dict, object_name: str,
                    upsert_key: str | None, write_mode: str, batch_size: int = 500) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    database = config.get("database")
    if not database:
        raise ValueError("mongodb destination requires 'database' in config")
    collection_name = object_name or config.get("collection")
    if not collection_name:
        raise ValueError("mongodb destination requires a destination_object (collection name)")

    client = _connect(config)
    success, failed, errors = 0, 0, []
    try:
        collection = client[database][collection_name]

        if write_mode == "upsert" and upsert_key:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                ops = [
                    UpdateOne({upsert_key: r.get(upsert_key)}, {"$set": r}, upsert=True)
                    for r in batch
                ]
                try:
                    result = collection.bulk_write(ops, ordered=False)
                    success += result.upserted_count + result.modified_count + result.matched_count
                except Exception as e:
                    failed += len(batch)
                    errors.append(str(e))
        else:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                try:
                    collection.insert_many(batch, ordered=False)
                    success += len(batch)
                except Exception as e:
                    failed += len(batch)
                    errors.append(str(e))
    finally:
        client.close()

    return {"success": success, "failed": failed, "errors": errors[:20]}
