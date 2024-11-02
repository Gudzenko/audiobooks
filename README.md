# audiobooks

Run dev:
docker-compose -f docker-compose.dev.yaml up --build

Run prod:
docker-compose -f docker-compose.prod.yaml up --build

Create super user
cd audiobooks
python .\manage.py createsuperuser

