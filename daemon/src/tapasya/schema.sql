-- Tapasya schema v1. Time is unix seconds (UTC); "day" is local YYYY-MM-DD.
CREATE TABLE IF NOT EXISTS samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    day         TEXT    NOT NULL,
    app_class   TEXT,
    title       TEXT,
    domain      TEXT,            -- filled from Brave extension (Phase 2)
    counted     INTEGER NOT NULL DEFAULT 0   -- 1 = counts as study
);
CREATE INDEX IF NOT EXISTS idx_samples_day ON samples(day);

CREATE TABLE IF NOT EXISTS goals (
    day            TEXT PRIMARY KEY,
    target_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
