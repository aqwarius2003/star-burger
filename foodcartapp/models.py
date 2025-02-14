from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator

from phonenumber_field.modelfields import PhoneNumberField
from django.db.models import Sum, F


class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = (
            RestaurantMenuItem.objects
            .filter(availability=True)
            .values_list('product')
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.TextField(
        'описание',
        max_length=200,
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='menu_items',
        verbose_name='продукт',
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True
    )

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class OrderManager(models.Manager):
    def get_total_price(self):
        return self.annotate(
            total_price=models.Sum(
                F('items__price') * F('items__quantity')
            )
        )


class Order(models.Model):
    UNPROCESSING = 'new'
    PROCESSING = 'prc'
    IN_DELEVERY = 'ind'
    ORDER_CLOSED = 'cls'
    ORDER_CANCELED = 'cnc'
    STATUS_CHOICES = [
        (UNPROCESSING, 'Необработанный'),
        (PROCESSING, 'Готовится'),
        (IN_DELEVERY, 'В доставке'),
        (ORDER_CLOSED, 'Заказ закрыт'),
        (ORDER_CANCELED, 'Заказ отменен')
    ]

    PAYMENT_METHODS = [
        ('card', 'Электронно'),
        ('cash', 'Наличные'),
    ]

    objects = OrderManager()

    firstname = models.CharField(
        verbose_name='Имя',
        max_length=25,
    )

    lastname = models.CharField(
        verbose_name='Фамилия',
        max_length=25
    )

    phonenumber = PhoneNumberField(
        verbose_name='контактный телефон',
        db_index=True
    )

    address = models.CharField(
        'Адрес доставки',
        max_length=120
    )

    payment_method = models.CharField(
        verbose_name="Способ оплаты",
        choices=PAYMENT_METHODS,
        max_length=4,
        default='card',
        db_index=True
    )

    registered_at = models.DateTimeField(
        verbose_name='Cоздан', default=timezone.now, db_index=True
    )

    called_at = models.DateTimeField(
        verbose_name='Время звонка', null=True, blank=True, db_index=True
    )
    delivery_at = models.DateTimeField(
        verbose_name='Время доставки', null=True, blank=True, db_index=True
    )

    status = models.CharField(
        max_length=3,
        verbose_name='Статус',
        choices=STATUS_CHOICES,
        default=UNPROCESSING,
        db_index=True
    )

    comments = models.TextField(
        verbose_name='Комментарии',
        blank=True,
        max_length=200
    )

    restaurant = models.ForeignKey(
        Restaurant,
        verbose_name='Ресторан',
        related_name='orders',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    price = OrderManager()

    class Meta:
        verbose_name = 'заказчик'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f"{self.firstname} {self.lastname} {self.address}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name='items',
        verbose_name='Заказ',
        on_delete=models.CASCADE
    )

    product = models.ForeignKey(
        Product,
        verbose_name='Продукт',
        on_delete=models.CASCADE,
        related_name="items",
    )

    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(1)]
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Цена'
    )

    class Meta:
        verbose_name = 'Пункт заказа'
        verbose_name_plural = 'заказы'

    def __str__(self):
        return f"OrderItem {self.product}: {self.quantity}"
