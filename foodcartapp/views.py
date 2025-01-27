from django.http import JsonResponse
from django.templatetags.static import static

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import (Product, Order, OrderItem)
from phonenumbers import parse, is_valid_number
from phonenumbers.phonenumberutil import NumberParseException


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


def validate_order_data(data):
    """
        Validates the incoming order data for required fields and correct data types.

        Args:
            data (dict): The data dictionary from the request.

        Returns:
            Response: A Response object with an error message and status code if validation fails.
        """

    # Проверяем наличие необходимых данных в карточке заказчика
    string_fields = ['firstname', 'lastname', 'phonenumber']
    for field in string_fields:
        if not isinstance(data.get(field), str):
            return Response(
                {"error": f"The key '{field}' is not specified or not str."},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Валидация номера телефона
    try:
        phonenumber = data.get("phonenumber")
        parsed_number = parse(phonenumber)
        if not is_valid_number(parsed_number):
            raise ValueError("The phonenumber is not valid")
    except (NumberParseException, ValueError):
        return Response(
            {"error": "The phonenumber is not valid"},
            status=status.HTTP_406_NOT_ACCEPTABLE
        )

    # Проверяем данные о продуктах
    if "products" not in data:
        return Response(
            {"error": "products: Обязательное поле."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    products = data.get("products")

    if products is None:
        return Response(
            {"error": "products: Это поле не может быть пустым."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(products, list):
        return Response(
            {"error": f"products: Ожидался list со значениями, но был получен {type(products).__name__}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not products:
        return Response(
            {"error": "products: Этот список не может быть пустым."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Проверяем наличие необходимых данных в карточке продукта
    product_ids = [product['product'] for product in products]
    existing_products = Product.objects.filter(id__in=product_ids)
    if len(product_ids) != len(existing_products):
        return Response(
            {"error": "products: Не все продукты с таким ID существуют"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


@api_view(['POST'])
def register_order(request):
    data = request.data

    error = validate_order_data(data)
    if error:
        return error
    # Получаем или создаем клиента(заказ)
    order, created = Order.objects.get_or_create(
        first_name=data['firstname'],
        last_name=data['lastname'],
        phone_number=data['phonenumber'],
        address=data.get('address')
    )

    # Создаем элементы заказа напрямую, используя ID продуктов из заказа
    order_items = [
        OrderItem(
            order=order,
            product_id=user_order['product'],
            quantity=user_order['quantity'],

        )
        for user_order in data['products']
    ]

    OrderItem.objects.bulk_create(order_items)
    return Response(data)
