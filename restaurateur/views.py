import requests
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q, Sum, F
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from requests import RequestException

from foodcartapp.models import Product, Restaurant, Order
from geopy.distance import distance


class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    products_with_restaurant_availability = []
    for product in products:
        availability = {item.restaurant_id: item.availability for item in product.menu_items.all()}
        ordered_availability = [availability.get(restaurant.id, False) for restaurant in restaurants]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurant_availability': products_with_restaurant_availability,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })


@user_passes_test(lambda user: user.is_staff, login_url='restaurateur:login')
def view_orders(request):
    orders = Order.objects.all().annotate(
        total_price=Sum(F('items__price') * F('items__quantity'))
    )
    available_restaurants_data = []

    # Определяем координаты каждого ресторана, сохраняем в переменной
    restaurants = Restaurant.objects.all()
    restaurant_coordinates = {}
    for restaurant in restaurants:
        location = fetch_coordinates(
            settings.YANDEX_GEOCODER_API_KEY,
            restaurant.address)
        if location:
            restaurant_coordinates[restaurant.id] = location[1], location[0]

    for order in orders:
        restaurant_distances = []
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
            customer_coordinates = fetch_coordinates(settings.YANDEX_GEOCODER_API_KEY, order.address)
            if customer_coordinates:
                customer_coordinates_lon_lat = (customer_coordinates[1],
                                                customer_coordinates[0])

                for restaurant in available_restaurants:
                    restaurant_distance_value = round(distance(
                        customer_coordinates_lon_lat,
                        restaurant_coordinates[restaurant.id]).km, 2)

                    restaurant_distances.append({
                        'name': restaurant.name,
                        'distance': restaurant_distance_value
                    })
                restaurant_distances.sort(key=lambda x: x['distance'])
                order.restaurant_distances = restaurant_distances
        except RequestException:
            print('Ошибка при определении координат')

        if restaurant_distances:
            available_restaurants_data.append(
                (order.id, restaurant_distances)
            )

    context = {
        'orders': orders,
        'excluded_statuses': ['cls', 'cnc'],
        'available_restaurants_data': available_restaurants_data,
    }
    return render(request, 'order_items.html', context)
