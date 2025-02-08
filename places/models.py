from django.db import models
from django.utils import timezone


class Place(models.Model):
    address = models.CharField(
        verbose_name='Адрес', max_length=200, unique=True
    )
    longitude = models.DecimalField(
        verbose_name='Долгота', max_digits=9, decimal_places=6, null=True, blank=True
    )
    latitude = models.DecimalField(
        verbose_name='Широта', max_digits=9, decimal_places=6, null=True, blank=True
    )
    create_date = models.DateTimeField(
        verbose_name='Дата изменения', default=timezone.now)

    class Meta:
        verbose_name = 'место'
        verbose_name_plural = 'места'

    def __str__(self):
        return self.address
