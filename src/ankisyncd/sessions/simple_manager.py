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
