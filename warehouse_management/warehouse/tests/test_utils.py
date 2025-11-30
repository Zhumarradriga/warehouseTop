import pytest

from warehouse.models import Placement, WarehouseJournal


@pytest.fixture
def create_placements(db, product, rack):
    """Создает несколько размещений для тестирования"""
    def _create_placements(quantities):
        placements = []
        for qty in quantities:
            placement = Placement.objects.create(
                rack=rack,
                product=product,
                quantity=qty,
                is_active=True
            )
            placements.append(placement)
        return placements
    return _create_placements


@pytest.fixture
def create_journal_entries(db, product, rack, batch):
    """Создает записи в журнале для тестирования"""
    def _create_entries(operations):
        entries = []
        for op_type, qty in operations:
            entry = WarehouseJournal.objects.create(
                operation_type=op_type,
                product=product,
                quantity=qty,
                rack=rack,
                batch=batch,
                operator="Тестовый оператор"
            )
            entries.append(entry)
        return entries
    return _create_entries
