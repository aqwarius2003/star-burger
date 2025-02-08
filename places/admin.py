from django.contrib import admin
from .models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'places'
    from django.contrib import admin

# Register your models here.
