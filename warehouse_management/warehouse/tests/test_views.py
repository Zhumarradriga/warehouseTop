import pytest
from django.urls import reverse
from django.utils import timezone
from warehouse.models import Placement, Product, WarehouseJournal


@pytest.mark.django_db
def test_dashboard_view(client, user):
    client.force_login(user)
    response = client.get(reverse('warehouse:dashboard'))
    assert response.status_code == 200
    assert 'total_products' in response.context
    assert 'total_racks' in response.context


@pytest.mark.django_db
def test_product_list_view(client, user, product):
    client.force_login(user)
    response = client.get(reverse('warehouse:product_list'))
    assert response.status_code == 200
    assert 'products' in response.context
    assert len(response.context['products']) == 1


@pytest.mark.django_db
def test_product_create_view(client, user, category):
    client.force_login(user)
    response = client.post(reverse('warehouse:product_create'), {
        'name': 'Новый товар',
        'category': category.id,
        'sku': 'NEW-001',
        'length': 10,
        'width': 5,
        'height': 2,
        'weight': 0.5
    })
    assert response.status_code == 302  # Redirect after successful creation
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_place_batch_view(client, user, batch, rack):
    client.force_login(user)

    # Проверяем GET запрос
    response = client.get(reverse('warehouse:place_batch',
                          kwargs={'batch_id': batch.id}))
    assert response.status_code == 200

    # Проверяем POST запрос для размещения товара
    response = client.post(reverse('warehouse:place_batch', kwargs={'batch_id': batch.id}), {
        'batch': batch.id,
        'rack': rack.id,
        'quantity': 10
    })

    assert response.status_code == 302  # Redirect after successful placement
    assert Placement.objects.count() == 1

    # Проверяем создание записи в журнале
    assert WarehouseJournal.objects.count() == 1
    journal_entry = WarehouseJournal.objects.first()
    assert journal_entry.operation_type == 'IN'
    assert journal_entry.quantity == 10


@pytest.mark.django_db
def test_issue_product_view(client, user, product, rack, batch):
    client.force_login(user)

    # Сначала размещаем товар на складе
    placement = Placement.objects.create(
        rack=rack,
        product=product,
        batch=batch,
        quantity=20,
        is_active=True
    )

    # Пытаемся выдать товар
    response = client.post(reverse('warehouse:issue_product'), {
        'product': product.id,
        'quantity': 5,
        'operator': 'Тестовый кладовщик'
    })

    assert response.status_code == 302  # Redirect after successful issue

    # Проверяем, что размещение обновлено
    placement.refresh_from_db()
    assert placement.quantity == 15
    assert placement.is_active is True

    # Проверяем запись в журнале
    assert WarehouseJournal.objects.filter(operation_type='OUT').count() == 1
    journal_entry = WarehouseJournal.objects.filter(
        operation_type='OUT').first()
    assert journal_entry.quantity == 5
    assert journal_entry.product == product
