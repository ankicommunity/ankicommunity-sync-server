# -*- coding: utf-8 -*-
import os
import logging
from sqlite3 import dbapi2 as sqlite

logger = logging.getLogger("ankisyncd.sessions")


class SimpleSessionManager:
    """A simple session manager that keeps the sessions in memory."""

    def __init__(self):
        self.sessions = {}

    def load(self, hkey, session_factory=None):
        return self.sessions.get(hkey)

    def load_from_skey(self, skey, session_factory=None):
        for i in self.sessions:
            if self.sessions[i].skey == skey:
                return self.sessions[i]

    def save(self, hkey, session):
        self.sessions[hkey] = session

    def delete(self, hkey):
        del self.sessions[hkey]


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
        cursor.execute("SELECT * FROM sqlite_master "
                       "WHERE sql LIKE '%user VARCHAR PRIMARY KEY%' "
                       "AND tbl_name = 'session'")
        res = cursor.fetchone()
        conn.close()
        if res is not None:
            raise Exception("Outdated database schema, run utils/migrate_user_tables.py")

    def _conn(self):
        new = not os.path.exists(self.session_db_path)
        conn = sqlite.connect(self.session_db_path)
        if new:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE session (hkey VARCHAR PRIMARY KEY, skey VARCHAR, username VARCHAR, path VARCHAR)")
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

        cursor.execute(self.fs("SELECT skey, username, path FROM session WHERE hkey=?"), (hkey,))
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

        cursor.execute(self.fs("SELECT hkey, username, path FROM session WHERE skey=?"), (skey,))
        res = cursor.fetchone()

        if res is not None:
            session = self.sessions[res[0]] = session_factory(res[1], res[2])
            session.skey = skey
            return session

    def save(self, hkey, session):
        SimpleSessionManager.save(self, hkey, session)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute("INSERT OR REPLACE INTO session (hkey, skey, username, path) VALUES (?, ?, ?, ?)",
            (hkey, session.skey, session.name, session.path))

        conn.commit()

    def delete(self, hkey):
        SimpleSessionManager.delete(self, hkey)

        conn = self._conn()
        cursor = conn.cursor()

        cursor.execute(self.fs("DELETE FROM session WHERE hkey=?"), (hkey,))
        conn.commit()

def get_session_manager(config):
    if "session_db_path" in config and config["session_db_path"]:
        logger.info("Found session_db_path in config, using SqliteSessionManager for auth")
        return SqliteSessionManager(config['session_db_path'])
    elif "session_manager" in config and config["session_manager"]:  # load from config
        logger.info("Found session_manager in config, using {} for persisting sessions".format(
            config['session_manager'])
        )
        import importlib
        import inspect
        module_name, class_name = config['session_manager'].rsplit('.', 1)
        module = importlib.import_module(module_name.strip())
        class_ = getattr(module, class_name.strip())

        if not SimpleSessionManager in inspect.getmro(class_):
            raise TypeError('''"session_manager" found in the conf file but it doesn''t
                            inherit from SimpleSessionManager''')
        return class_(config)
    else:
        logger.warning("Neither session_db_path nor session_manager set, "
                     "ankisyncd will lose sessions on application restart")
        return SimpleSessionManager()
