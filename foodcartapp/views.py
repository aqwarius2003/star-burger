from django.http import JsonResponse
from django.templatetags.static import static
import json


from .models import Product, Customer, OrderItem


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


def register_order(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode())

        # Получаем или создаем клиента
        customer, created = Customer.objects.get_or_create(
            first_name=data['firstname'],
            last_name=data['lastname'],
            phone_number=data['phonenumber'],
        )
        # Проверяем наличие адреса
        address = data.get('address')
        if not address:
            return JsonResponse({'error': 'Address is required'}, status=400)

        # Создаем элементы заказа напрямую, используя ID продуктов из заказа
        order_items = [
            OrderItem(
                product_id=user_order['product'],
                quantity=user_order['quantity'],
                customer=customer
            )
            for user_order in data['products']
        ]

        OrderItem.objects.bulk_create(order_items)
    return JsonResponse({})
