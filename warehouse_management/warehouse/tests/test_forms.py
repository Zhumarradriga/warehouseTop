import pytest
from django.core.exceptions import ValidationError
from warehouse.forms import PlacementForm, IssueForm, CheckCapacityForm
from warehouse.models import Placement, Rack


@pytest.mark.django_db
def test_placement_form_validation(batch, rack):
    # Тест валидной формы
    form_data = {
        'batch': batch.id,
        'rack': rack.id,
        'quantity': 5
    }

    form = PlacementForm(data=form_data, batch_id=batch.id)
    assert form.is_valid()

    # Тест невалидной формы - количество больше доступного
    form_data['quantity'] = batch.quantity + 1
    form = PlacementForm(data=form_data, batch_id=batch.id)
    assert not form.is_valid()
    # Ошибка будет в общих ошибках формы (__all__), а не в поле quantity
    assert '__all__' in form.errors
    assert 'Нельзя разместить больше товара, чем осталось в партии' in str(
        form.errors['__all__'][0])


@pytest.mark.django_db
def test_issue_form_validation(product):
    # Создаем размещение для тестирования
    rack = Rack.objects.create(
        name="Тест стеллаж",
        max_load=100,
        length=100,
        width=50,
        height=200
    )

    Placement.objects.create(
        rack=rack,
        product=product,
        quantity=10,
        is_active=True
    )

    # Тест валидной формы
    form_data = {
        'product': product.id,
        'quantity': 5,
        'operator': 'Тест кладовщик'
    }

    form = IssueForm(data=form_data)
    assert form.is_valid()

    # Тест невалидной формы - количество больше доступного
    form_data['quantity'] = 15
    form = IssueForm(data=form_data)
    assert not form.is_valid()
    assert '__all__' in form.errors
    assert 'Недостаточно товара на складе' in str(form.errors['__all__'][0])


@pytest.mark.django_db
def test_check_capacity_form_validation(product):
    form_data = {
        'product': product.id,
        'quantity': 10
    }

    form = CheckCapacityForm(data=form_data)
    assert form.is_valid()

    # Тест с отрицательным количеством
    form_data['quantity'] = -5
    form = CheckCapacityForm(data=form_data)
    assert not form.is_valid()
    assert 'quantity' in form.errors
