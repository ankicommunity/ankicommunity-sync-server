import os
from sqlite3 import dbapi2 as sqlite
from ankisyncd.sessions.simple_manager import SimpleSessionManager


class SqliteSessionManager(SimpleSessionManager):
    """Stores sessions in a SQLite database to prevent the user from being logged out
    everytime the SyncApp is restarted."""

    def __init__(self, session_db_path):
        super().__init__()

        self.session_db_path = os.path.realpath(session_db_path)
        self._ensure_schema_up_to_date()

    def _ensure_schema_up_to_date(self):
        if not os.path.exists(self.session_db_path):
            return True

        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sqlite_master "
            "WHERE sql LIKE '%user VARCHAR PRIMARY KEY%' "
            "AND tbl_name = 'session'"
        )
        res = cursor.fetchone()
        conn.close()
        if res is not None:
            raise Exception(
                "Outdated database schema, run utils/migrate_user_tables.py"
            )

    def _conn(self):
        new = not os.path.exists(self.session_db_path)
        conn = sqlite.connect(self.session_db_path)
        if new:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE session (hkey VARCHAR PRIMARY KEY, skey VARCHAR, username VARCHAR, path VARCHAR)"
            )
        return conn

    # Default to using sqlite3 syntax but overridable for sub-classes using other
    # DB API 2 driver variants
    @staticmethod
    def fs(sql):
        return sql

    def load(self, hkey, session_factory=None):
        session = SimpleSessionManager.load(self, hkey)
        if session is not None:
            return session

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute(
            self.fs("SELECT skey, username, path FROM session WHERE hkey=?"), (hkey,)
        )
        res = cursor.fetchone()

        if res is not None:
            session = self.sessions[hkey] = session_factory(res[1], res[2])
            session.skey = res[0]
            return session

    def load_from_skey(self, skey, session_factory=None):
        session = SimpleSessionManager.load_from_skey(self, skey)
        if session is not None:
            return session

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute(
            self.fs("SELECT hkey, username, path FROM session WHERE skey=?"), (skey,)
        )
        res = cursor.fetchone()

        if res is not None:
            session = self.sessions[res[0]] = session_factory(res[1], res[2])
            session.skey = skey
            return session

    def save(self, hkey, session):
        SimpleSessionManager.save(self, hkey, session)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO session (hkey, skey, username, path) VALUES (?, ?, ?, ?)",
            (hkey, session.skey, session.name, session.path),
        )

        conn.commit()

    def delete(self, hkey):
        SimpleSessionManager.delete(self, hkey)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute(self.fs("DELETE FROM session WHERE hkey=?"), (hkey,))
        conn.commit()
