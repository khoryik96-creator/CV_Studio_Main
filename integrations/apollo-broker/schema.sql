-- Separate hosted sign-in state; never the CV Studio user database.
CREATE TABLE IF NOT EXISTS flows (
  id TEXT PRIMARY KEY, proof TEXT NOT NULL, status TEXT NOT NULL,
  expires INTEGER NOT NULL, created INTEGER NOT NULL, ip_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS flows_expiry ON flows(expires);
CREATE INDEX IF NOT EXISTS flows_rate ON flows(ip_hash,created);
CREATE TABLE IF NOT EXISTS connections (
  id TEXT PRIMARY KEY, proof TEXT NOT NULL, cipher TEXT NOT NULL,
  expires INTEGER NOT NULL, busy INTEGER NOT NULL DEFAULT 0,
  reauth INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS connections_expiry ON connections(expires);
CREATE TABLE IF NOT EXISTS operations (
  connection_id TEXT NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
  id TEXT NOT NULL, fingerprint TEXT NOT NULL, state TEXT NOT NULL,
  cipher TEXT NOT NULL DEFAULT '', expires INTEGER NOT NULL,
  PRIMARY KEY(connection_id,id)
);
CREATE INDEX IF NOT EXISTS operations_expiry ON operations(expires);
