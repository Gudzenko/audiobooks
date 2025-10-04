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
