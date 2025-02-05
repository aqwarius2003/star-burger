from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import reverse
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import models
from django.db.models import Count, Q

from .models import (
    Order,
    OrderItem,
    Restaurant,
    Product,
    RestaurantMenuItem,
    ProductCategory,
)
from star_burger.settings import ALLOWED_HOSTS


class RestaurantMenuItemInline(admin.TabularInline):
    model = RestaurantMenuItem
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'address',
        'contact_phone',
    ]
    list_display = [
        'name',
        'address',
        'contact_phone',
    ]
    inlines = [
        RestaurantMenuItemInline
    ]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'get_image_list_preview',
        'name',
        'category',
        'price',
    ]
    list_display_links = [
        'name',
    ]
    list_filter = [
        'category',
    ]
    search_fields = [
        # FIXME SQLite can not convert letter case for cyrillic words properly, so search will be buggy.
        # Migration to PostgreSQL is necessary
        'name',
        'category__name',
    ]

    inlines = [
        RestaurantMenuItemInline
    ]
    fieldsets = (
        ('Общее', {
            'fields': [
                'name',
                'category',
                'image',
                'get_image_preview',
                'price',
            ]
        }),
        ('Подробно', {
            'fields': [
                'special_status',
                'description',
            ],
            'classes': [
                'wide'
            ],
        }),
    )

    readonly_fields = [
        'get_image_preview',
    ]

    class Media:
        css = {
            "all": (
                static("admin/foodcartapp.css")
            )
        }

    def get_image_preview(self, obj):
        if not obj.image:
            return 'выберите картинку'
        return format_html('<img src="{url}" style="max-height: 200px;"/>', url=obj.image.url)

    get_image_preview.short_description = 'превью'

    def get_image_list_preview(self, obj):
        if not obj.image or not obj.id:
            return 'нет картинки'
        edit_url = reverse('admin:foodcartapp_product_change', args=(obj.id,))
        return format_html(
            '<a href="{edit_url}"><img src="{src}" style="max-height: 50px;"/></a>',
            edit_url=edit_url, src=obj.image.url)

    get_image_list_preview.short_description = 'превью'


@admin.register(ProductCategory)
class ProductAdmin(admin.ModelAdmin):
    pass


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    feilds = [
        'product',
        'quantity',
    ]
    short_description = 'Заказанные товары'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [
        OrderItemInline
    ]
    list_display = [
        'firstname',
        'lastname',
        'address',
    ]

    def save_formset(self, request, form, formset, change):
        order_items = formset.save(commit=False)
        for item in order_items:
            if item.price == 0.00:
                product = Product.objects.get(id=item.product.id)
                item.price = product.price
                item.save()
            else:
                item.save()

    def response_post_save_change(self, request, obj):
        res = super().response_post_save_change(request, obj)
        if "next" in request.GET and url_has_allowed_host_and_scheme(
            request.GET['next'],
            ALLOWED_HOSTS
        ):
            return HttpResponseRedirect(request.GET['next'])
        else:
            return res

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "restaurant":
            # Получаем ID товаров из запроса (если они уже добавлены в заказ)
            order_id = request.resolver_match.kwargs.get('object_id')
            if order_id:
                order = Order.objects.get(pk=order_id)
                product_ids = order.items.values_list('product_id', flat=True)
            else:
                # Если это новый заказ, то пока нет товаров
                product_ids = []

            # Если есть товары в заказе, фильтруем рестораны
            if product_ids:
                # Получаем рестораны, у которых есть *все* товары из заказа в меню *и* они доступны
                available_restaurants = Restaurant.objects.annotate(
                    num_matching_products=Count(
                        'menu_items',
                        filter=Q(menu_items__product_id__in=product_ids) & Q(menu_items__availability=True)
                    )
                ).filter(num_matching_products=len(product_ids)).distinct()

                kwargs["queryset"] = available_restaurants
            else:
                # Если товаров нет, показываем все рестораны
                kwargs["queryset"] = Restaurant.objects.all()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
