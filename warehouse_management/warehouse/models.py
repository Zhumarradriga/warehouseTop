
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, verbose_name='Категория')
    sku = models.CharField(max_length=50, unique=True, verbose_name='Артикул')
    length = models.FloatField(help_text="Длина в см", verbose_name='Длина')
    width = models.FloatField(help_text="Ширина в см", verbose_name='Ширина')
    height = models.FloatField(help_text="Высота в см", verbose_name='Высота')
    weight = models.FloatField(help_text="Вес в кг", verbose_name='Вес')
    image = models.ImageField(
        upload_to='products/', blank=True, null=True, verbose_name='Изображение товара')

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_volume(self):
        return self.length * self.width * self.height

    def image_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return '/static/images/default-product.png'


class Rack(models.Model):
    name = models.CharField(max_length=50, unique=True,
                            verbose_name='Название')
    max_load = models.FloatField(
        help_text="Максимальная нагрузка в кг", verbose_name='Максимальный вес')
    length = models.FloatField(help_text="Длина в см", verbose_name='Длина')
    width = models.FloatField(help_text="Ширина в см", verbose_name='Ширина')
    height = models.FloatField(help_text="Высота в см", verbose_name='Высота')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Стелаж'
        verbose_name_plural = 'Стелажы'

    def __str__(self):
        return self.name

    @property
    def volume(self):
        return self.length * self.width * self.height

    def can_fit_product(self, product, quantity=1):
        """Проверка, поместится ли продукт на стеллаж"""
        # Проверка по габаритам
        if (product.length <= self.length and
            product.width <= self.width and
                product.height <= self.height):
            # Проверка по весу
            if product.weight * quantity <= self.max_load:
                return True
        return False

    def available_volume(self):
        """Расчет свободного объема на стеллаже"""
        occupied_volume = sum(
            placement.quantity * placement.product.get_volume()
            for placement in self.placements.filter(is_active=True)
        )
        return self.volume - occupied_volume

    def available_weight(self):
        """Расчет доступной нагрузки на стеллаже"""
        occupied_weight = sum(
            placement.quantity * placement.product.weight
            for placement in self.placements.filter(is_active=True)
        )
        return self.max_load - occupied_weight

    def get_utilization_percent(self):
        """Процент заполнения стеллажа"""
        if self.volume == 0:
            return 0
        occupied_volume = self.volume - self.available_volume()
        return round((occupied_volume / self.volume) * 100, 1)


class Batch(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name='Товар')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    arrival_date = models.DateTimeField(
        default=timezone.now, verbose_name='Дата привоза')
    supplier = models.CharField(max_length=200, verbose_name='Поставщик')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Партия'
        verbose_name_plural = 'Партиии'

    def __str__(self):
        return f"Партия {self.product.name} x {self.quantity} от {self.arrival_date.date()}"

    def get_initial_remaining(self):
        """Возвращает количество товара из партии, которое еще не было размещено изначально"""
        total_placed = self.placement_set.aggregate(
            total=Sum('quantity'))['total'] or 0
        return max(0, self.quantity - total_placed)

    def get_actual_remaining(self):
        """Возвращает количество товара из партии, которое еще не было размещено"""
        total_placed = self.placement_set.filter(
            is_active=True).aggregate(total=Sum('quantity'))['total'] or 0
        return max(0, self.quantity - total_placed)

    def is_fully_processed(self):
        """Проверяет, полностью ли обработана партия (размещена и выдана)"""
        return self.is_fully_placed() and self.get_available_for_issue() == 0

    def is_fully_placed(self):
        """Проверяет, полностью ли размещена партия (независимо от выдачи)"""
        return self.get_initial_remaining() <= 0

    def get_available_for_issue(self):
        """Возвращает количество товара из партии, доступное для выдачи"""
        # Считаем общее количество размещено из этой партии
        total_placed = self.placement_set.aggregate(
            total=Sum('quantity'))['total'] or 0

        # Считаем количество выдано из этой партии
        total_issued = self.warehousejournal_set.filter(
            operation_type='OUT'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return max(0, total_placed - total_issued)


class Placement(models.Model):
    rack = models.ForeignKey(
        Rack, on_delete=models.CASCADE, related_name='placements', verbose_name='Стелаж')
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name='Товар')
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Партия')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    date_placed = models.DateTimeField(
        default=timezone.now, verbose_name='Дата размещения')
    # Активное размещение или нет (если товар был выдан)
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Размещение'
        verbose_name_plural = 'Размещения'

    def __str__(self):
        return f"{self.product.name} x {self.quantity} на {self.rack.name}"


class WarehouseJournal(models.Model):
    OPERATION_CHOICES = [
        ('IN', 'Приход'),
        ('OUT', 'Расход'),
    ]

    operation_type = models.CharField(
        max_length=3, choices=OPERATION_CHOICES, verbose_name='Тип операции')
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name='Товар')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    rack = models.ForeignKey(
        Rack, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Стелаж')
    batch = models.ForeignKey(
        Batch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Партия')
    operation_date = models.DateTimeField(
        default=timezone.now, verbose_name='Дата  операции')
    operator = models.CharField(max_length=100, verbose_name='Оператор')
    notes = models.TextField(blank=True, null=True, verbose_name='Описание')

    def __str__(self):
        return f"{self.operation_type} - {self.product.name} x {self.quantity}"

    class Meta:
        ordering = ['-operation_date']
        verbose_name = 'Операция'
        verbose_name_plural = 'Операции'
