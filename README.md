# audiobooks

Add file .env
Add dir static in audiobooks

Run dev:
docker compose -f docker-compose.dev.yaml up --build

Run isolated local development environment:

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

Run the browser test for sequential audio uploads:

```bash
docker compose -f docker-compose.local.yaml --profile browser-tests \
  run --rm --build browser-tests
```

The test uses a dedicated browser-test database, logs in as the seeded local admin,
uploads two small fixture files, verifies the book page, and removes the book.

Run prod:

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

Create super user
cd audiobooks
python .\manage.py createsuperuser

Generate translateion files
in docker container
python manage.py compilemessages

# Problems

1. Full Disk (No Space Left)

Check disk usage:

df -h

If using Docker:

docker system df
docker system prune -a

Verify space:

df -h

2. External Drive Mounted with New Name

When the drive mounts as ADATA_HM9001 instead of ADATA_HM900:

sudo umount /media/pi/ADATA_HM9001
sudo rm -rf /media/pi/ADATA_HM900

Unplug and reconnect the drive.
It should now mount as /media/pi/ADATA_HM900
