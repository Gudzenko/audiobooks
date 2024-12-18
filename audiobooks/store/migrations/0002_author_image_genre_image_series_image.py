# Generated by Django 4.2.16 on 2024-11-11 10:29

from django.db import migrations, models
import store.utils


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='author',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=store.utils.author_image_upload_path),
        ),
        migrations.AddField(
            model_name='genre',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=store.utils.genre_image_upload_path),
        ),
        migrations.AddField(
            model_name='series',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=store.utils.series_image_upload_path),
        ),
    ]
