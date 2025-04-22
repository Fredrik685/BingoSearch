import sqlite3

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name

    def fetch_data(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Fetch column names
        cursor.execute("PRAGMA table_info(info)")
        columns = [row[1] for row in cursor.fetchall()]

        # Fetch data
        query = "SELECT * FROM info"
        cursor.execute(query)
        data = cursor.fetchall()

        conn.close()
        return columns, data

    def update_record(self, record_id, **kwargs):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Construct the SQL update query dynamically
        columns = self.get_columns()
        set_clause = ', '.join([f"{col} = ?" for col in kwargs.keys() if col in columns])
        query = f"UPDATE info SET {set_clause} WHERE id = ?"
        values = list(kwargs.values()) + [record_id]

        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def delete_record(self, record_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM info WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

    def add_record(self, **kwargs):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Get columns from the database
        columns = self.get_columns()

        # Filter kwargs to include only valid columns
        valid_kwargs = {k: v for k, v in kwargs.items() if k in columns}

        # Construct the SQL insert query dynamically
        cols = ', '.join(valid_kwargs.keys())
        placeholders = ', '.join(['?' for _ in valid_kwargs])
        query = f"INSERT INTO info ({cols}) VALUES ({placeholders})"
        values = list(valid_kwargs.values())
#        values = [valid_kwargs.get(col, None) for col in columns]



        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def get_columns(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Fetch column names
        cursor.execute("PRAGMA table_info(info)")
        columns = [row[1] for row in cursor.fetchall()]

        conn.close()
        return columns
