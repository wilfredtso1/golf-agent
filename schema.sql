CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Players: standing profiles that persist across sessions
CREATE TABLE IF NOT EXISTS players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  phone TEXT UNIQUE NOT NULL,
  general_availability JSONB NOT NULL DEFAULT '[]'::jsonb,
  course_preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
  standing_constraints TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT players_phone_e164_chk CHECK (phone ~ '^[+][1-9][0-9]{7,14}$')
);

-- Sessions: one per coordination round
CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_player_id UUID REFERENCES players(id),
  target_date DATE NOT NULL,
  candidate_courses JSONB NOT NULL,
  session_code TEXT,
  status TEXT NOT NULL DEFAULT 'collecting',
  form_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT sessions_status_chk CHECK (status IN ('collecting', 'searching', 'proposing', 'confirmed', 'closed', 'expired')),
  CONSTRAINT sessions_session_code_chk CHECK (session_code IS NULL OR session_code ~ '^[0-9]{2,4}$')
);

ALTER TABLE sessions
  ADD COLUMN IF NOT EXISTS session_code TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'sessions_session_code_chk'
  ) THEN
    ALTER TABLE sessions
      ADD CONSTRAINT sessions_session_code_chk
      CHECK (session_code IS NULL OR session_code ~ '^[0-9]{2,4}$');
  END IF;
END$$;

-- Session players: per-player responses within a session
CREATE TABLE IF NOT EXISTS session_players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'invited',
  available_time_blocks JSONB NOT NULL DEFAULT '[]'::jsonb,
  approved_courses JSONB NOT NULL DEFAULT '[]'::jsonb,
  invited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  responded_at TIMESTAMPTZ,
  reminder_sent_at TIMESTAMPTZ,
  UNIQUE(session_id, player_id),
  CONSTRAINT session_players_status_chk CHECK (status IN ('invited', 'confirmed', 'declined', 'unresponsive'))
);

-- Courses: canonical catalog + latest observed market snapshot
CREATE TABLE IF NOT EXISTS courses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  default_booking_url TEXT,
  latest_price_per_player NUMERIC,
  latest_currency TEXT NOT NULL DEFAULT 'USD',
  latest_seen_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tee time proposals: options found and proposed to lead
CREATE TABLE IF NOT EXISTS tee_time_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  course TEXT NOT NULL,
  tee_time TIMESTAMPTZ NOT NULL,
  price_per_player NUMERIC,
  booking_url TEXT,
  status TEXT NOT NULL DEFAULT 'proposed',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT tee_time_proposals_status_chk CHECK (status IN ('proposed', 'selected', 'expired'))
);

-- Messages: conversation log per player per session
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
  player_id UUID REFERENCES players(id) ON DELETE SET NULL,
  direction TEXT NOT NULL,
  body TEXT NOT NULL,
  provider_message_sid TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT messages_direction_chk CHECK (direction IN ('inbound', 'outbound'))
);

CREATE UNIQUE INDEX IF NOT EXISTS messages_inbound_sid_uidx
  ON messages(provider_message_sid)
  WHERE direction = 'inbound' AND provider_message_sid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_players_phone ON players(phone);
CREATE INDEX IF NOT EXISTS idx_courses_name ON courses(name);
CREATE INDEX IF NOT EXISTS idx_sessions_session_code_status ON sessions(session_code, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_active_session_code
  ON sessions(session_code)
  WHERE session_code IS NOT NULL
    AND status IN ('collecting', 'searching', 'proposing');
CREATE INDEX IF NOT EXISTS idx_session_players_session_id ON session_players(session_id);
CREATE INDEX IF NOT EXISTS idx_session_players_player_id ON session_players(player_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status_created_at ON sessions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_player_created_at
  ON messages(session_id, player_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_player_created_at
  ON messages(player_id, created_at DESC);

DROP TRIGGER IF EXISTS players_set_updated_at ON players;
CREATE TRIGGER players_set_updated_at
BEFORE UPDATE ON players
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS sessions_set_updated_at ON sessions;
CREATE TRIGGER sessions_set_updated_at
BEFORE UPDATE ON sessions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS courses_set_updated_at ON courses;
CREATE TRIGGER courses_set_updated_at
BEFORE UPDATE ON courses
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
