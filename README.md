# audiobooks

Add file .env
Add dir static in audiobooks

Run dev:
docker compose -f docker-compose.dev.yaml up --build

Run prod:
docker compose -f docker-compose.prod.yaml up --build

Create super user
cd audiobooks
python .\manage.py createsuperuser

Generate translateion files
in docker container
python manage.py compilemessages
