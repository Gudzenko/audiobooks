# audiobooks

The application manages a local audiobook catalog and exposes it through the
web interface, a read-only MCP endpoint and an authenticated chat assistant.

The legacy development environment that uses host paths can be started with:

```bash
docker compose -f docker-compose.dev.yaml up --build
```

For normal development, use the isolated local environment:

```bash
docker compose -f docker-compose.local.yaml up --build
```

Open http://localhost:8000/store/ and sign in with:

- email: `admin@example.com`
- username: `admin`
- password: `admin`

The local environment uses separate Docker volumes for its SQLite database
and media files. It does not read or modify the production database.

The local MCP endpoint is `http://localhost:8000/mcp/`. It uses the existing
user accounts and JWT authentication. Obtain tokens with the local admin
credentials:

```bash
curl -X POST http://localhost:8000/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin"}'
```

Use the returned `access` token when connecting an MCP client:

```text
Authorization: Bearer <access token>
```

When it expires, send the returned `refresh` token to `/auth/token/refresh/`
to obtain a new access token. In production, use a normal application user;
do not store an administrator password in an MCP client.

Stop it without deleting the test database:

```bash
docker compose -f docker-compose.local.yaml down
```

Run all browser tests:

```bash
docker compose -f docker-compose.local.yaml --profile browser-tests \
  up -d --build --force-recreate browser-web
docker compose -f docker-compose.local.yaml --profile browser-tests \
  run --rm --build browser-tests
```

The browser suite uses dedicated `browser_test_database` and
`browser_test_media` volumes. It does not access the local development or
production database. The suite checks sequential audio uploads and the chat UI,
including catalog results, clarification, external-service failure, rich text,
links and in-memory history. Chat browser tests use mock providers and do not
spend OpenAI or Exa credits.

Run all Django tests inside the local application container:

```bash
docker compose -f docker-compose.local.yaml exec -T web \
  python manage.py test --keepdb
```

## Production-like smoke environment

Run an isolated production-like copy on http://localhost:8080/:

```bash
docker compose -p audiobooks-smoke -f docker-compose.smoke.yaml up -d --build
```

It uses the production Dockerfile, Uvicorn workers and Nginx, but has separate
Docker volumes for its database, media, static files and backups. It creates
only three test books and two tiny WAV files; it never reads production data.

Sign in with email `smoke@example.com` and password `smoke`. The username is
`smoke`. Stop the environment without deleting its data:

```bash
docker compose -p audiobooks-smoke -f docker-compose.smoke.yaml down
```

Delete only the isolated smoke data and recreate it from scratch:

```bash
docker compose -p audiobooks-smoke -f docker-compose.smoke.yaml down -v
```

## Production

The production `.env` file must contain a non-empty `SECRET_KEY`,
`ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`. Both host settings accept
comma-separated lists. Keep the existing secret key when updating an
installation so current sessions and JWTs remain valid.

```bash
docker compose -f docker-compose.prod.yaml up --build
```

Before applying production migrations, create and verify a SQLite backup:

```bash
docker compose -f docker-compose.prod.yaml run --rm \
  --entrypoint python web manage.py backup_database
```

Backups are written to `./backups/` on the host. Only after the backup command
has completed successfully, stop the application before changing the SQLite
schema:

```bash
docker compose -f docker-compose.prod.yaml stop web
```

Then run migrations explicitly:

```bash
docker compose -f docker-compose.prod.yaml run --rm \
  --entrypoint python web manage.py migrate
```

Start the application again after a successful migration:

```bash
docker compose -f docker-compose.prod.yaml up -d web nginx
```

Starting or restarting the production application no longer runs migrations
automatically.

## Large audiobook uploads

When several audio files are selected for a book, the browser first saves the
book metadata and then uploads each file in a separate request. Failed files
can be retried without sending the complete book again. Existing books can
also receive more audio files from their edit page.

Requests use at most 10 MiB of in-memory buffering. Larger files are staged in
`/app/media/.upload_tmp`, which is located on the media volume, and Nginx does
not create a second buffered request body for the audio upload endpoint. The
temporary directory is not publicly accessible. Because the production media
disk uses FAT, a single audio file is limited to 4 GB; the combined size of a
book may be larger.

After an interrupted container or host shutdown, inspect stale temporary files
without deleting them:

```bash
docker compose -f docker-compose.prod.yaml run --rm \
  --entrypoint python web manage.py cleanup_upload_temp --dry-run
```

Remove temporary upload files older than 24 hours:

```bash
docker compose -f docker-compose.prod.yaml run --rm \
  --entrypoint python web manage.py cleanup_upload_temp
```

## Deferred operations

These maintenance tasks are intentionally deferred:

- Schedule `backup_database` and copy verified backups off the Raspberry Pi.
  Define retention before enabling the schedule so old copies cannot fill the
  system disk. Audio files are not included in the SQLite backup.
- Schedule `cleanup_upload_temp` after uploads have been observed in production
  for a while. Run it in `--dry-run` mode first and delete only files older than
  the agreed retention period.

Cron or a systemd timer can run either command later. The command itself must
remain usable manually so scheduled execution is only an operational wrapper.

## MCP and chat

The MCP endpoint remains part of the Django ASGI application and uses the same
catalog services and user accounts. It should not become a separate service at
this stage.

### Architecture

Authenticated users can open `/store/chat/`. The chat calls the real
read-only `search_books` MCP tool through FastMCP's in-memory transport, so it
does not make an HTTP request back to the application. Chat-model and web-search
providers are selected independently through environment variables. Mock
providers remain the default, so development and tests never spend API credits.

The orchestration layer does not depend directly on OpenAI or Exa. Provider
protocols define planning, answer generation, list extraction, title matching
and web search. The current adapters are:

- `mock` for deterministic local development and automated tests;
- `openai` for query planning, structured extraction, title matching and final
  answers;
- `exa` for web search and retrieval of relevant public pages.

The chat can search the local catalog, search public web sources, inspect a
public site named in the question, and compare external titles with local book
cards. Title matching may use translated names, alternative names and
transliteration. External links are shown as sources; the application does not
download books or authenticate on third-party sites.

Conversation history exists only in the browser's JavaScript memory. Reloading
or closing the page clears it; no messages are stored in the database, Django
session, cookies or local storage. The message endpoint requires the existing
Django login and CSRF protection.

To test the real OpenAI and Exa adapters locally, create an ignored `.env` file
next to `docker-compose.local.yaml` using `.env.example` as a reference:

```dotenv
CHAT_MODEL_PROVIDER=openai
WEB_SEARCH_PROVIDER=exa
OPENAI_API_KEY=replace-with-your-key
OPENAI_MODEL=gpt-6-luna
EXA_API_KEY=replace-with-your-key
```

Then rebuild the local container. Never add real keys to Compose files, source
code, browser JavaScript, logs or Git. OpenAI creates the tool plan and final
answer; Exa supplies external search results. Either adapter can be replaced by
implementing the corresponding provider protocol. If Exa is unavailable, the
chat returns a clearly marked partial answer based on the local catalog.

Search limits are controlled separately: `CHAT_WEB_RESULT_LIMIT` is used for
ordinary searches and `CHAT_SITE_RESULT_LIMIT` for inventory-style searches on
a named site. `CHAT_CATALOG_RESULT_LIMIT` limits the total number of local books
returned to one chat request. `CHAT_WEB_CONTENT_MAX_CHARS` limits full text
loaded from each external page, while `CHAT_WEB_CONTENT_TOTAL_MAX_CHARS` limits
the combined text sent for list extraction. `CHAT_PROVIDER_TIMEOUT` limits
provider calls. `CHAT_REQUESTS_PER_MINUTE` limits paid requests per
authenticated user. A file lock prevents concurrent requests from the same
user for the full request lifetime. Rate-limit state contains counters only and is stored in
`CHAT_RATE_LIMIT_DIR`; it contains no message text. A result may still be
incomplete when the public source is incomplete, unavailable, blocked or not
fully indexed; the response must report that limitation instead of claiming
that the list is exhaustive.

OpenAI output is also bounded separately for planning, clarification, ordinary
answers, list extraction and title matching through the corresponding
`CHAT_*_MAX_OUTPUT_TOKENS` settings. These limits include visible output and
model reasoning tokens.

### Current boundaries

- The chat and MCP catalog tools are read-only.
- Conversation history exists only until the page is reloaded or cleared.
- Local comparison is based on book cards and available metadata; the contents
  of a collection cannot be inferred when they are absent from the catalog.
- External sources are public pages only. Links must still be reviewed by the
  user before relying on them.
- Write-capable MCP tools, audit logging, confirmations for destructive actions,
  provider metrics and scheduled maintenance remain future work.

## Development commands

Create a superuser outside Docker:

```bash
cd audiobooks
python manage.py createsuperuser
```

Compile translation files inside the application container:

```bash
python manage.py compilemessages
```

## Troubleshooting

### No space left on device

Check disk usage:

```bash
df -h
```

If using Docker:

```bash
docker system df
docker system prune -a
```

Verify space:

```bash
df -h
```

### External drive mounted with a new name

When the drive mounts as ADATA_HM9001 instead of ADATA_HM900:

```bash
sudo umount /media/pi/ADATA_HM9001
sudo rm -rf /media/pi/ADATA_HM900
```

Unplug and reconnect the drive.
It should now mount as /media/pi/ADATA_HM900
