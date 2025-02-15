import logging

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from geopy.distance import distance
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from places.models import Place
from places.views import fetch_coordinates
from .models import Order, OrderItem, Restaurant

logger = logging.getLogger(__name__)


class OrderItemSerializer(ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(many=True, allow_empty=False, write_only=True)

    class Meta:
        model = Order
        fields = ['firstname', 'lastname', 'phonenumber', 'address', 'products']

    def create(self, validated_data):
        # Извлекаем продукты из validated_data, чтобы передать их отдельно
        products_data = validated_data.pop('products')

        # Используем super() для создания объекта Order без поля 'products'
        order = super(OrderSerializer, self).create(validated_data)

        # Создаем элементы заказа (OrderItem) с привязкой к заказу
        order_items = []
        for product_data in products_data:
            product = product_data['product']
            price = product.price  # Получаем цену из модели Product
            order_item = OrderItem(order=order, price=price, **product_data)
            order_items.append(order_item)

        # Создаем все элементы заказа за один запрос
        OrderItem.objects.bulk_create(order_items)

        # Обновляем или создаем Place (адрес)
        try:
            Place.objects.update_or_create(
                address=order.address, defaults={"create_date": timezone.now()}
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении или создании места для адреса {order.address}: {str(e)}")

        return order


def update_or_create_place(address):
    place, created = Place.objects.get_or_create(address=address)
    if created or not place.latitude or not place.longitude:
        location = fetch_coordinates(settings.YANDEX_GEOCODER_API_KEY, address)
        if location:
            longitude, latitude = location
            place.longitude = longitude
            place.latitude = latitude
            place.save()
        else:
            logger.warning(f"Не удалось получить координаты для адреса {address} из API")
    else:
        logger.info(f"Координаты для адреса {address} загружены из базы данных")


def get_coordinates(address, place_map, api_key):
    place = place_map.get(address)
    if place and place.latitude and place.longitude:
        return place.latitude, place.longitude
    else:
        update_or_create_place(address)
        place = place_map.get(address)
        return (place.latitude, place.longitude) if place else None


def process_restaurants(restaurants, place_map, api_key):
    restaurant_coordinates = {}
    for restaurant in restaurants:
        coordinates = get_coordinates(restaurant.address, place_map, api_key)
        if coordinates:
            restaurant_coordinates[restaurant.id] = coordinates
        else:
            logger.warning(f"Не удалось получить координаты для ресторана {restaurant.name} из API")
    return restaurant_coordinates


def get_available_restaurants(order):
    if order.restaurant:
        return [order.restaurant]
    else:
        # Если ресторан не выбран, ищем подходящие рестораны
        product_ids = order.items.values_list('product_id', flat=True)
        return Restaurant.objects.annotate(
            num_matching_products=Count(
                'menu_items',
                filter=Q(menu_items__product_id__in=product_ids) & Q(menu_items__availability=True)
            )
        ).filter(num_matching_products=len(product_ids)).distinct() if product_ids else Restaurant.objects.all()


def process_orders(orders, restaurant_coordinates, place_map, api_key):
    available_restaurants_data = []
    orders_to_update = []  # Список для сбора заказов, которые нужно обновить

    for order in orders:
        restaurant_distances = []
        customer_coordinates = get_coordinates(order.address, place_map, api_key)
        if customer_coordinates:
            available_restaurants = get_available_restaurants(order)
            for restaurant in available_restaurants:
                if restaurant.id in restaurant_coordinates:
                    restaurant_distance_value = round(distance(
                        customer_coordinates,
                        restaurant_coordinates[restaurant.id]).km, 2)
                    restaurant_distances.append({
                        'name': restaurant.name,
                        'distance': restaurant_distance_value
                    })
                else:
                    logger.warning(f"Предупреждение: Нет координат для ресторана {restaurant.name}")
            restaurant_distances.sort(key=lambda x: x['distance'])
            order.restaurant_distances = restaurant_distances

            # Проверяем, нужно ли обновить статус заказа
            if order.restaurant and order.status != Order.PROCESSING:
                order.status = Order.PROCESSING
                orders_to_update.append(order)

        available_restaurants_data.append((order.id, restaurant_distances))

    # После цикла, массовое обновление статуса
    if orders_to_update:
        Order.objects.bulk_update(orders_to_update, ['status'])

    return available_restaurants_data


def load_coordinates(addresses):
    place_map = {place.address: place for place in Place.objects.filter(address__in=addresses)}
    updated_places = []

    for address in addresses:
        update_or_create_place(address)
        place = place_map.get(address)
        if place:
            updated_places.append(place)

    return place_map, updated_places


def update_coordinates_on_address_change(instance, new_address):
    if instance.address != new_address:
        update_or_create_place(new_address)
        place = Place.objects.get(address=new_address)
        if place:
            instance.address = new_address
            instance.longitude = place.longitude
            instance.latitude = place.latitude
            instance.save()
            logger.info(f"Координаты для адреса {new_address} обновлены")
        else:
            logger.warning(f"Не удалось обновить координаты для нового адреса {new_address}")
