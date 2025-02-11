from django.db import migrations, models

def set_default_comments(apps, schema_editor):
    Order = apps.get_model('foodcartapp', 'Order')
    for order in Order.objects.filter(comments__isnull=True):
        order.comments = ""
        order.save()



class Migration(migrations.Migration):

    dependencies = [
        ('foodcartapp', '0045_order_restaurant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='comments',
            field=models.TextField(
                verbose_name='Комментарии',
                blank=True,
                max_length=200,
                null=False,
            ),
        ),
        migrations.RunPython(set_default_comments),
    ]
