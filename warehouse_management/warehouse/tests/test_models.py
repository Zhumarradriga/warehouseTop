import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from warehouse.models import Category, Product, Rack, Batch, Placement, WarehouseJournal


@pytest.mark.django_db
def test_category_creation():
    category = Category.objects.create(name="Тестовая категория")
    assert category.name == "Тестовая категория"
    assert str(category) == "Тестовая категория"


@pytest.mark.django_db
def test_product_creation(category):
    product = Product.objects.create(
        name="Тестовый товар",
        category=category,
        sku="TEST-001",
        length=10,
        width=5,
        height=2,
        weight=1.5
    )
    assert product.name == "Тестовый товар"
    assert product.get_volume() == 100  # 10 * 5 * 2
    assert str(product) == "Тестовый товар (TEST-001)"


@pytest.mark.django_db
def test_rack_methods(rack, product):
    # Проверка расчета объема
    assert rack.volume == 1000000  # 100 * 50 * 200

    # Проверка возможности размещения товара
    assert rack.can_fit_product(product) is True

    # Проверка доступного объема (изначально весь объем свободен)
    assert rack.available_volume() == rack.volume

    # Проверка доступной нагрузки
    assert rack.available_weight() == rack.max_load

    # Проверка процента использования
    assert rack.get_utilization_percent() == 0.0


@pytest.mark.django_db
def test_batch_methods(product):
    batch = Batch.objects.create(
        product=product,
        quantity=100,
        arrival_date=timezone.now(),
        supplier="Тестовый поставщик"
    )

    # Изначально ничего не размещено
    assert batch.get_initial_remaining() == 100
    assert batch.get_actual_remaining() == 100
    assert batch.get_available_for_issue() == 0
    assert batch.is_fully_placed() is False
    assert batch.is_fully_processed() is False

    # После частичного размещения
    # (имитация размещения 30 единиц)
    batch.placement_set.create(
        product=product,
        quantity=30,
        rack=Rack.objects.create(
            name="Тест", max_load=50, length=100, width=50, height=50)
    )

    assert batch.get_initial_remaining() == 70
    assert batch.is_fully_placed() is False

    # После полного размещения
    batch.placement_set.create(
        product=product,
        quantity=70,
        rack=Rack.objects.create(
            name="Тест2", max_load=100, length=200, width=100, height=100)
    )

    assert batch.get_initial_remaining() == 0
    assert batch.is_fully_placed() is True
