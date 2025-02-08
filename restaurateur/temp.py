from places.models import Place  # Импортируем модель Place
from places.views import fetch_coordinates  # Импортируем функцию fetch_coordinates
from django.conf import settings
from django.db.models import Sum, F, Count, Q
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from foodcartapp.models import Order, Restaurant
from requests import RequestException
from geopy.distance import distance


@user_passes_test(lambda user: user.is_staff, login_url='restaurateur:login')
def view_orders(request):
    orders = Order.objects.all().annotate(
        total_price=Sum(F('items__price') * F('items__quantity'))
    )

    available_restaurants_data = []

    # Получаем все рестораны и их координаты из базы данных Place
    restaurants = Restaurant.objects.all()

    #  Получаем все адреса ресторанов и заказов одним запросом к БД
    addresses = set(restaurant.address for restaurant in restaurants)
    addresses.update(order.address for order in orders)

    # Инициализируем place_map пустым словарем
    place_map = {}

    # Получаем все Place объекты для этих адресов одним запросом
    places = Place.objects.filter(address__in=addresses)
    place_map = {place.address: place for place in places}

    restaurant_coordinates = {}
    for restaurant in restaurants:
        place = place_map.get(restaurant.address)
        if place and place.latitude and place.longitude:
            restaurant_coordinates[restaurant.id] = (place.latitude, place.longitude)
        else:
            # Если координаты не найдены в Place, получаем их из API и сохраняем в Place
            location = fetch_coordinates(settings.YANDEX_GEOCODER_API_KEY, restaurant.address)
            if location:
                longitude, latitude = location
                # Создаем Place, если его еще нет
                if not place:
                    place = Place.objects.create(address=restaurant.address, longitude=longitude, latitude=latitude)
                else:
                    place.longitude = longitude
                    place.latitude = latitude
                    place.save()
                place_map[restaurant.address] = place  # Обновляем кэш
                restaurant_coordinates[restaurant.id] = (latitude, longitude)
            else:
                print(f"Не удалось получить координаты для ресторана {restaurant.name} из API")

    for order in orders:
        restaurant_distances = []
        customer_coordinates = None  # Изначально координат нет

        if order.restaurant:
            available_restaurants = [order.restaurant]
            order.status = Order.PROCESSING
            order.save()
        else:
            product_ids = order.items.values_list('product_id', flat=True)
            available_restaurants = Restaurant.objects.annotate(
                num_matching_products=Count(
                    'menu_items',
                    filter=Q(menu_items__product_id__in=product_ids) & Q(menu_items__availability=True)
                )
            ).filter(num_matching_products=len(product_ids)).distinct() if product_ids else Restaurant.objects.all()

        try:
            # Ищем координаты заказчика в Place
            place = place_map.get(order.address)
            if place and place.latitude and place.longitude:
                customer_coordinates = (place.latitude, place.longitude)
            else:
                # Если координат нет в Place, получаем из API и сохраняем
                location = fetch_coordinates(settings.YANDEX_GEOCODER_API_KEY, order.address)
                if location:
                    longitude, latitude = location
                    # Создаем Place, если его еще нет
                    if not place:
                        place = Place.objects.create(address=order.address, longitude=longitude, latitude=latitude)
                    else:
                        place.longitude = longitude
                        place.latitude = latitude
                        place.save()
                    place_map[order.address] = place  # Обновляем кэш
                    customer_coordinates = (latitude, longitude)
                else:
                    print(f"Не удалось получить координаты для адреса заказа {order.address} из API")

            if customer_coordinates:
                customer_coordinates_lon_lat = customer_coordinates

                for restaurant in available_restaurants:
                    if restaurant.id in restaurant_coordinates:
                        restaurant_distance_value = round(distance(
                            customer_coordinates_lon_lat,
                            restaurant_coordinates[restaurant.id]).km, 2)

                        restaurant_distances.append({
                            'name': restaurant.name,
                            'distance': restaurant_distance_value
                        })
                    else:
                        print(f"Предупреждение: Нет координат для ресторана {restaurant.name}")
                        continue

                restaurant_distances.sort(key=lambda x: x['distance'])
                order.restaurant_distances = restaurant_distances
        except RequestException:
            print('Ошибка при определении координат')

        if restaurant_distances:
            available_restaurants_data.append(
                (order.id, restaurant_distances)
            )
        else:
            available_restaurants_data.append(
                (order.id, [])
            )

    context = {
        'orders': orders,
        'excluded_statuses': ['cls', 'cnc'],
        'available_restaurants_data': available_restaurants_data,
    }
    return render(request, 'order_items.html', context)
