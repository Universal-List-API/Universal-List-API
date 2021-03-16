CREATE TABLE bot_list (
	icon TEXT,
	url TEXT NOT NULL UNIQUE,
	api_url TEXT,
	discord TEXT,
	description TEXT,
	supported_features INTEGER[],
	api_token TEXT,
	queue BOOLEAN DEFAULT FALSE,
	owners BIGINT[] DEFAULT '{}'
);

CREATE TABLE bot_list_feature (
	name TEXT NOT NULL UNIQUE,
	iname TEXT NOT NULL UNIQUE, -- Internal Name
	description TEXT,
	positive INTEGER
);

CREATE TABLE bot_list_api (
	url TEXT NOT NULL,
	method INTEGER, -- 1 = GET, 2 = POST, 3 = PATCH, 4 = PUT, 5 = DELETE
	feature INTEGER, -- 1 = Get Bot, 2 = Post Stats
	supported_fields JSONB, -- Supported fields
	api_path TEXT NOT NULL,
	CONSTRAINT url_constraint FOREIGN KEY (url) REFERENCES bot_list(url) ON DELETE CASCADE ON UPDATE CASCADE -- Autoupdate
);
