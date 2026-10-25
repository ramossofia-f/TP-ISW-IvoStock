CREATE TABLE providers (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, url TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'new', active BOOLEAN NOT NULL DEFAULT TRUE,
 next_run_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_error TEXT,
 last_accepted_run BIGINT
);
CREATE TABLE stores (
 id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'importing',
 blocked_until TIMESTAMPTZ NOT NULL DEFAULT now(), last_error TEXT
);
CREATE TABLE catalog (
 store_id TEXT NOT NULL REFERENCES stores, item_id TEXT NOT NULL, sku TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity >= 0), PRIMARY KEY(store_id,item_id)
);
CREATE INDEX catalog_sku ON catalog(store_id,sku);
CREATE TABLE runs (
 id BIGSERIAL PRIMARY KEY, provider_id BIGINT NOT NULL REFERENCES providers,
 status TEXT NOT NULL DEFAULT 'running', snapshot_key TEXT, metrics JSONB NOT NULL DEFAULT '{}',
 error TEXT, replay_of BIGINT REFERENCES runs, started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 finished_at TIMESTAMPTZ
);
CREATE TABLE stock (
 provider_id BIGINT NOT NULL REFERENCES providers, sku TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity >= 0), PRIMARY KEY(provider_id,sku)
);
CREATE TABLE links (
 id BIGSERIAL PRIMARY KEY, provider_id BIGINT NOT NULL REFERENCES providers,
 store_id TEXT NOT NULL, item_id TEXT NOT NULL, sku TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','error','inactive')),
 cut_requested BOOLEAN NOT NULL DEFAULT FALSE, desired INTEGER NOT NULL CHECK(desired>=0),
 confirmed INTEGER NOT NULL CHECK(confirmed>=0), revision BIGINT NOT NULL DEFAULT 1,
 last_success_at TIMESTAMPTZ, last_error TEXT,
 FOREIGN KEY(store_id,item_id) REFERENCES catalog
);
CREATE UNIQUE INDEX single_writer ON links(store_id,item_id) WHERE state != 'inactive';
CREATE TABLE comparison_events (
 id BIGSERIAL PRIMARY KEY, provider_id BIGINT NOT NULL REFERENCES providers,
 run_id BIGINT REFERENCES runs, processed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX unprocessed_events ON comparison_events(id) WHERE processed_at IS NULL;
CREATE TABLE tasks (
 link_id BIGINT PRIMARY KEY REFERENCES links, revision BIGINT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity>=0), attempts INTEGER NOT NULL DEFAULT 0,
 enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now(), available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 claimed_until TIMESTAMPTZ, claimed_revision BIGINT, replacements INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE attempts (
 id BIGSERIAL PRIMARY KEY, link_id BIGINT NOT NULL REFERENCES links, revision BIGINT NOT NULL,
 quantity INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'in_flight', http_status INTEGER,
 response TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ
);
CREATE TABLE dead_letters (
 id BIGSERIAL PRIMARY KEY, link_id BIGINT NOT NULL REFERENCES links,
 attempt_id BIGINT REFERENCES attempts, revision BIGINT NOT NULL, quantity INTEGER NOT NULL,
 http_status INTEGER, response TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 reviewed_at TIMESTAMPTZ
);
CREATE TABLE market_calls (store_id TEXT NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp());
CREATE INDEX market_calls_window ON market_calls(store_id,at);
CREATE TABLE worker_heartbeats (name TEXT PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE sim_stores (id TEXT PRIMARY KEY);
CREATE TABLE sim_items (
 store_id TEXT NOT NULL REFERENCES sim_stores, id TEXT NOT NULL, sku TEXT NOT NULL,
 available_quantity INTEGER NOT NULL CHECK(available_quantity>=0),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), writes BIGINT NOT NULL DEFAULT 0,
 PRIMARY KEY(store_id,id)
);
CREATE TABLE sim_calls (store_id TEXT NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp());
CREATE INDEX sim_calls_window ON sim_calls(store_id,at);
CREATE TABLE sim_faults (
 store_id TEXT NOT NULL, item_id TEXT NOT NULL DEFAULT '*', status INTEGER NOT NULL,
 remaining INTEGER NOT NULL, PRIMARY KEY(store_id,item_id)
);
