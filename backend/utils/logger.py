import psycopg2
from datetime import datetime

class DBLogger:

    def __init__(self, conn, run_id):
        self.conn = conn
        self.cursor = conn.cursor()
        self.run_id = run_id

    def log(self, level, message):
        self.cursor.execute("""
            INSERT INTO pipeline_logs (run_id, log_time, level, message)
            VALUES (%s, %s, %s, %s)
        """, (self.run_id, datetime.now(), level, message))
        self.conn.commit()