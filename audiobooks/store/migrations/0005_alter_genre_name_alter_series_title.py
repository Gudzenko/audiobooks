# Generated by Django 4.2.16 on 2024-11-24 17:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0004_audiofile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='genre',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='series',
            name='title',
            field=models.CharField(max_length=200),
        ),
    ]