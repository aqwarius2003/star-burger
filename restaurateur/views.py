import logging

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum, F
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from foodcartapp.models import Order, Product, Restaurant
from foodcartapp.serializers import process_orders, process_restaurants
from places.models import Place


logger = logging.getLogger(__name__)

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
    orders = Order.objects.select_related('restaurant').prefetch_related('items').annotate(
        total_price=Sum(F('items__price') * F('items__quantity'))
    )

    restaurants = Restaurant.objects.all()
    addresses = set(restaurant.address for restaurant in restaurants)
    addresses.update(order.address for order in orders)
    place_map = {place.address: place for place in Place.objects.filter(address__in=addresses)}
    api_key = settings.YANDEX_GEOCODER_API_KEY

    restaurant_coordinates = process_restaurants(restaurants, place_map, api_key)
    available_restaurants_data = process_orders(orders, restaurant_coordinates, place_map, api_key)

    context = {
        'orders': orders,
        'excluded_statuses': ['cls', 'cnc'],
        'available_restaurants_data': available_restaurants_data,
    }
    return render(request, 'order_items.html', context)
