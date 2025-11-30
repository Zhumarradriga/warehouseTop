from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.db import transaction
from .models import Product, Rack, Batch, Placement, WarehouseJournal, Category
from .forms import ProductForm, RackForm, BatchForm, PlacementForm, IssueForm, CheckCapacityForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required


class DashboardView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request):
        # Статистика склада
        total_products = Product.objects.count()
        total_racks = Rack.objects.filter(is_active=True).count()
        active_placements = Placement.objects.filter(is_active=True).count()
        total_quantity = Placement.objects.filter(
            is_active=True).aggregate(total=Sum('quantity'))['total'] or 0

        # Товары с низким остатком
        low_stock_products = []
        for product in Product.objects.all():
            quantity = Placement.objects.filter(product=product, is_active=True).aggregate(
                total=Sum('quantity'))['total'] or 0
            if quantity < 10:  # Порог низкого остатка
                low_stock_products.append({
                    'product': product,
                    'quantity': quantity
                })

        # Последние операции
        recent_operations = WarehouseJournal.objects.all()[:10]

        # Загруженность стеллажей
        racks_utilization = []
        for rack in Rack.objects.filter(is_active=True).order_by('name')[:5]:
            racks_utilization.append({
                'rack': rack,
                'utilization': rack.get_utilization_percent()
            })

        context = {
            'total_products': total_products,
            'total_racks': total_racks,
            'active_placements': active_placements,
            'total_quantity': total_quantity,
            'low_stock_products': low_stock_products[:5],
            'recent_operations': recent_operations,
            'racks_utilization': racks_utilization,
        }
        return render(request, 'warehouse/dashboard.html', context)


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'warehouse/product_list.html'
    context_object_name = 'products'
    paginate_by = 20


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'warehouse/product_form.html'
    success_url = reverse_lazy('warehouse:product_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'warehouse/product_form.html'
    success_url = reverse_lazy('warehouse:product_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs


class RackListView(LoginRequiredMixin, ListView):
    model = Rack
    template_name = 'warehouse/rack_list.html'
    context_object_name = 'racks'


class RackCreateView(LoginRequiredMixin, CreateView):
    model = Rack
    form_class = RackForm
    template_name = 'warehouse/rack_form.html'
    success_url = reverse_lazy('warehouse:rack_list')


class RackUpdateView(LoginRequiredMixin, UpdateView):
    model = Rack
    form_class = RackForm
    template_name = 'warehouse/rack_form.html'
    success_url = reverse_lazy('warehouse:rack_list')


class BatchCreateView(LoginRequiredMixin, View):
    def get(self, request):
        form = BatchForm()
        return render(request, 'warehouse/batch_form.html', {'form': form})

    def post(self, request):
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save()
            messages.success(
                request, f'Партия товара "{batch.product.name}" успешно создана')
            return redirect('warehouse:suggest_racks', batch_id=batch.id)
        return render(request, 'warehouse/batch_form.html', {'form': form})


class BatchListView(LoginRequiredMixin, ListView):
    model = Batch
    template_name = 'warehouse/batch_list.html'
    context_object_name = 'batches'
    ordering = ['-arrival_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Аннотируем каждую партию количеством размещенного товара
        queryset = queryset.annotate(
            placed_quantity=Sum('placement__quantity',
                                filter=Q(placement__is_active=True))
        )
        return queryset


class SuggestRacksView(LoginRequiredMixin, View):
    def get(self, request, batch_id):
        batch = get_object_or_404(Batch, id=batch_id)
        product = batch.product

        # Проверяем, полностью ли размещена партия
        if batch.is_fully_placed():
            messages.info(request, 'Вся партия уже была размещена на складе')
            return redirect('warehouse:batch_list')

        # Вычисляем оставшееся количество для первоначального размещения
        remaining_quantity = batch.get_initial_remaining()

        # Считаем, сколько товара из партии в данный момент активно размещено
        placed_quantity = batch.quantity - remaining_quantity

        # Алгоритм подбора стеллажей...
        racks = Rack.objects.filter(is_active=True)
        suggested_racks = []

        # Сортируем стеллажи по доступному объему
        sorted_racks = sorted(
            racks, key=lambda x: x.available_volume(), reverse=True)
        remaining = remaining_quantity

        for rack in sorted_racks:
            if remaining <= 0:
                break
            # Проверяем, подходит ли товар по габаритам
            if not rack.can_fit_product(product):
                continue

            # Рассчитываем, сколько товара можно разместить на стеллаже
            max_by_volume = int(rack.available_volume() //
                                product.get_volume())
            max_by_weight = int(rack.available_weight() // product.weight)
            max_quantity = min(max_by_volume, max_by_weight)

            if max_quantity > 0:
                quantity_to_place = min(max_quantity, remaining)
                suggested_racks.append({
                    'rack': rack,
                    'max_quantity': max_quantity,
                    'suggested_quantity': quantity_to_place
                })
                remaining -= quantity_to_place

        context = {
            'batch': batch,
            'suggested_racks': suggested_racks,
            'remaining_quantity': remaining,
            'already_placed': placed_quantity,
        }
        return render(request, 'warehouse/suggest_racks.html', context)


class PlaceBatchView(LoginRequiredMixin, View):
    def get(self, request, batch_id):
        batch = get_object_or_404(Batch, id=batch_id)

        # Проверка, полностью ли размещена партия
        if batch.is_fully_placed():
            messages.info(request, 'Вся партия уже размещена на складе')
            return redirect('warehouse:batch_list')

        # Вычисляем оставшееся количество для размещения
        remaining_quantity = batch.get_initial_remaining()
        placed_quantity = batch.quantity - remaining_quantity

        form = PlacementForm(batch_id=batch_id)

        # Если переданы параметры в URL, устанавливаем значения по умолчанию
        rack_id = request.GET.get('rack_id')
        quantity = request.GET.get('quantity')

        if rack_id:
            try:
                form.fields['rack'].initial = int(rack_id)
            except (ValueError, TypeError):
                pass

        if quantity:
            try:
                # Ограничиваем предложенное количество доступным остатком
                form.fields['quantity'].initial = min(
                    int(quantity), remaining_quantity)
            except (ValueError, TypeError):
                pass

        context = {
            'form': form,
            'batch': batch,
            'placed_quantity': placed_quantity,
            'remaining_quantity': remaining_quantity,
        }
        return render(request, 'warehouse/place_batch.html', context)

    @transaction.atomic
    def post(self, request, batch_id):
        batch = get_object_or_404(Batch, id=batch_id)
        form = PlacementForm(request.POST, batch_id=batch_id)

        # Проверка, полностью ли размещена партия
        if batch.is_fully_placed():
            messages.error(
                request, 'Невозможно разместить товар: вся партия уже была размещена на складе')
            return redirect('warehouse:batch_list')

        # Проверяем оставшееся количество для размещения
        remaining_quantity = batch.get_initial_remaining()
        if remaining_quantity <= 0:
            messages.error(
                request, 'Невозможно разместить товар: в партии не осталось товара для размещения')
            return redirect('warehouse:batch_list')

        if form.is_valid():
            rack = form.cleaned_data['rack']
            quantity = form.cleaned_data['quantity']

            # Проверяем, не превышает ли запрашиваемое количество доступное для размещения
            if quantity > remaining_quantity:
                messages.error(
                    request, f'Невозможно разместить указанное количество. В партии осталось только {remaining_quantity} ед. для размещения')
                return render(request, 'warehouse/place_batch.html', {
                    'form': form,
                    'batch': batch,
                    'placed_quantity': batch.quantity - remaining_quantity,
                    'remaining_quantity': remaining_quantity
                })

            product = batch.product

            # Создаем размещение
            placement = Placement.objects.create(
                rack=rack,
                product=product,
                batch=batch,
                quantity=quantity,
                is_active=True
            )

            # Создаем запись в журнале
            WarehouseJournal.objects.create(
                operation_type='IN',
                product=product,
                quantity=quantity,
                rack=rack,
                batch=batch,
                operator=request.user.username if request.user.is_authenticated else 'Кладовщик',
                notes=f'Размещение партии #{batch.id}'
            )

            messages.success(
                request, f'Успешно размещено {quantity} ед. товара {product.name} на стеллаже {rack.name}')

            # Проверяем, полностью ли размещена партия после этой операции
            if batch.is_fully_placed():
                messages.success(
                    request, 'Вся партия успешно размещена на складе')
                return redirect('warehouse:batch_list')
            else:
                return redirect('warehouse:suggest_racks', batch_id=batch.id)

        # Если форма невалидна
        remaining_quantity = batch.get_initial_remaining()
        placed_quantity = batch.quantity - remaining_quantity
        return render(request, 'warehouse/place_batch.html', {
            'form': form,
            'batch': batch,
            'placed_quantity': placed_quantity,
            'remaining_quantity': remaining_quantity
        })


class IssueProductView(LoginRequiredMixin, View):
    def get(self, request):
        form = IssueForm()
        return render(request, 'warehouse/issue_form.html', {'form': form})

    @transaction.atomic
    def post(self, request):
        form = IssueForm(request.POST)

        if form.is_valid():
            product = form.cleaned_data['product']
            quantity = form.cleaned_data['quantity']
            operator = form.cleaned_data['operator']
            remaining_quantity = quantity

            # Получаем размещения товара, сортируем по дате (FIFO - первый пришел, первый ушел)
            placements = Placement.objects.filter(
                product=product,
                is_active=True
            ).order_by('date_placed')

            if not placements.exists():
                messages.error(request, 'Товар отсутствует на складе')
                return render(request, 'warehouse/issue_form.html', {'form': form})

            # Списываем товар со стеллажей
            for placement in placements:
                if remaining_quantity <= 0:
                    break

                if placement.quantity >= remaining_quantity:
                    # Частичное списание с текущего размещения
                    WarehouseJournal.objects.create(
                        operation_type='OUT',
                        product=product,
                        quantity=remaining_quantity,
                        rack=placement.rack,
                        operator=operator,
                        notes=f'Частичная выдача товара'
                    )
                    placement.quantity -= remaining_quantity
                    placement.save()
                    remaining_quantity = 0
                else:
                    # Полное списание текущего размещения
                    remaining_quantity -= placement.quantity
                    WarehouseJournal.objects.create(
                        operation_type='OUT',
                        product=product,
                        quantity=placement.quantity,
                        rack=placement.rack,
                        operator=operator,
                        notes=f'Полная выдача товара'
                    )
                    placement.is_active = False
                    placement.save()

            if remaining_quantity > 0:
                messages.warning(
                    request, f'Не удалось выдать весь запрошенный объем. Выдано: {quantity - remaining_quantity} из {quantity}')
            else:
                messages.success(
                    request, f'Успешно выдано {quantity} ед. товара {product.name}')

            return redirect('warehouse:issue_product')

        return render(request, 'warehouse/issue_form.html', {'form': form})


class CheckCapacityView(LoginRequiredMixin, View):
    def get(self, request):
        form = CheckCapacityForm()
        return render(request, 'warehouse/check_capacity.html', {'form': form})

    def post(self, request):
        form = CheckCapacityForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            quantity = form.cleaned_data['quantity']
            # Алгоритм проверки вместимости
            available_racks = Rack.objects.filter(is_active=True)
            # Сортируем стеллажи по доступному объему
            racks = sorted(available_racks,
                           key=lambda x: x.available_volume(), reverse=True)
            remaining_quantity = quantity
            suggested_racks = []
            for rack in racks:
                if remaining_quantity <= 0:
                    break
                # Проверяем, подходит ли товар по габаритам
                if not rack.can_fit_product(product):
                    continue
                # Расчет максимального количества товара, которое можно разместить на стеллаже
                max_by_volume = int(
                    rack.available_volume() // product.get_volume())
                max_by_weight = int(rack.available_weight() // product.weight)
                max_quantity = min(max_by_volume, max_by_weight)
                if max_quantity > 0:
                    quantity_to_place = min(max_quantity, remaining_quantity)
                    suggested_racks.append({
                        'rack': rack,
                        'quantity': quantity_to_place,
                        'max_possible': max_quantity,
                        'utilization_after': (rack.volume - (rack.available_volume() - product.get_volume() * quantity_to_place)) / rack.volume * 100
                    })
                    remaining_quantity -= quantity_to_place

            can_store = remaining_quantity == 0
            # Вычисляем размещенное количество
            placed_quantity = quantity - remaining_quantity

            context = {
                'form': form,
                'can_store': can_store,
                'suggested_racks': suggested_racks,
                'remaining_quantity': remaining_quantity,
                'placed_quantity': placed_quantity,  # Передаем вычисленное значение
                'product': product,
                'requested_quantity': quantity
            }
            return render(request, 'warehouse/check_capacity_result.html', context)
        return render(request, 'warehouse/check_capacity.html', {'form': form})


class SearchProductView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '')
        products = []
        placements = []

        if query:
            # Поиск товаров по названию, SKU или категории
            products = Product.objects.filter(
                Q(name__icontains=query) |
                Q(sku__icontains=query) |
                Q(category__name__icontains=query)
            ).distinct()

            # Получаем размещения для найденных товаров
            placements = Placement.objects.filter(
                product__in=products,
                is_active=True
            ).select_related('rack', 'product', 'batch')

        context = {
            'query': query,
            'products': products,
            'placements': placements
        }
        return render(request, 'warehouse/search_product.html', context)


class WarehouseJournalView(LoginRequiredMixin, ListView):
    model = WarehouseJournal
    template_name = 'warehouse/journal.html'
    context_object_name = 'entries'
    ordering = ['-operation_date']
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        operation_type = self.request.GET.get('operation_type')
        product = self.request.GET.get('product')
        operator = self.request.GET.get('operator')

        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)
        if product:
            queryset = queryset.filter(product__name__icontains=product)
        if operator:
            queryset = queryset.filter(operator__icontains=operator)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Передаем текущие значения фильтров в контекст
        context['operation_type_filter'] = self.request.GET.get(
            'operation_type', '')
        context['product_filter'] = self.request.GET.get('product', '')
        context['operator_filter'] = self.request.GET.get('operator', '')
        # Предвычисляем условия для выбора опций в селекте
        context['is_in_selected'] = self.request.GET.get(
            'operation_type') == 'IN'
        context['is_out_selected'] = self.request.GET.get(
            'operation_type') == 'OUT'
        return context
