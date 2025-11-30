import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from warehouse.models import Category, Product, Rack, Batch


@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def category(db):
    return Category.objects.create(name="Электроника", description="Электронные товары")


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        name="Смартфон",
        category=category,
        sku="SMART-001",
        length=15,
        width=7,
        height=1,
        weight=0.2
    )


@pytest.fixture
def rack(db):
    return Rack.objects.create(
        name="Стеллаж-A1",
        max_load=100,
        length=100,
        width=50,
        height=200,
        is_active=True
    )


@pytest.fixture
def batch(db, product):
    return Batch.objects.create(
        product=product,
        quantity=50,
        arrival_date=timezone.now(),
        supplier="Поставщик ООО"
    )
