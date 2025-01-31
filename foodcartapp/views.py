from django.http import JsonResponse
from django.templatetags.static import static

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import (Product, Order, OrderItem)
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers


class OrderItemSerializer(ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(many=True, allow_empty=False)

    class Meta:
        model = Order
        fields = ['firstname', 'lastname', 'phonenumber', 'address', 'products']


def banners_list_api(request):
    # FIXME move data to db?
    return JsonResponse([
        {
            'title': 'Burger',
            'src': static('burger.jpg'),
            'text': 'Tasty Burger at your door step',
        },
        {
            'title': 'Spices',
            'src': static('food.jpg'),
            'text': 'All Cuisines',
        },
        {
            'title': 'New York',
            'src': static('tasty.jpg'),
            'text': 'Food is incomplete without a tasty dessert',
        }
    ], safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


def product_list_api(request):
    products = Product.objects.select_related('category').available()

    dumped_products = []
    for product in products:
        dumped_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'special_status': product.special_status,
            'description': product.description,
            'category': {
                'id': product.category.id,
                'name': product.category.name,
            } if product.category else None,
            'image': product.image.url,
            'restaurant': {
                'id': product.id,
                'name': product.name,
            }
        }
        dumped_products.append(dumped_product)
    return JsonResponse(dumped_products, safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


@api_view(['POST'])
def register_order(request):
    serializer = OrderSerializer(data=request.data)
    if serializer.is_valid():

        # Получаем или создаем клиента(заказ)
        order_data = {
            'firstname': serializer.validated_data['firstname'],
            'lastname': serializer.validated_data['lastname'],
            'phonenumber': serializer.validated_data['phonenumber'],
            'address': serializer.validated_data['address']
        }

        order, created = Order.objects.get_or_create(**order_data)

        # Создаем элементы заказа напрямую, используя ID продуктов из заказа
        products_fields = serializer.validated_data['products']
        products = [OrderItem(order=order, **fields) for fields in products_fields]

        OrderItem.objects.bulk_create(products)
        # Возвращаем данные о заказе
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        # Возвращаем номер ошибки и сообщение об ошибке
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
