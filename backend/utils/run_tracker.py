from datetime import datetime

class RunTracker:

    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def start_run(self, connector, source):
        self.cursor.execute("""
            INSERT INTO pipeline_runs (connector_name, source, start_time, status)
            VALUES (%s, %s, %s, %s)
            RETURNING run_id
        """, (connector, source, datetime.now(), "RUNNING"))

        run_id = self.cursor.fetchone()[0]
        self.conn.commit()
        return run_id

    def end_run(self, run_id, status, count=0, error=None):
        self.cursor.execute("""
            UPDATE pipeline_runs
            SET end_time=%s, status=%s, records_count=%s, error=%s
            WHERE run_id=%s
        """, (datetime.now(), status, count, error, run_id))

        self.conn.commit()