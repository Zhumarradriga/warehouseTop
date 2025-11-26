from django import forms
from .models import Product, Rack, Batch, Placement, WarehouseJournal
from django.db.models import Sum
from django.core.exceptions import ValidationError

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

class RackForm(forms.ModelForm):
    class Meta:
        model = Rack
        fields = '__all__'

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['product', 'quantity', 'supplier', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

class PlacementForm(forms.Form):
    batch = forms.ModelChoiceField(queryset=Batch.objects.none(), label='Партия')
    rack = forms.ModelChoiceField(queryset=Rack.objects.filter(is_active=True), label='Стеллаж')
    quantity = forms.IntegerField(min_value=1, label='Количество для размещения')
    
    def __init__(self, *args, **kwargs):
        batch_id = kwargs.pop('batch_id', None)
        super().__init__(*args, **kwargs)
        if batch_id:
            self.fields['batch'].queryset = Batch.objects.filter(id=batch_id)
            self.fields['batch'].initial = batch_id
            
            try:
                batch = Batch.objects.get(id=batch_id)
                remaining_quantity = batch.get_initial_remaining()
                
                self.fields['quantity'].widget.attrs['max'] = remaining_quantity
                self.fields['quantity'].widget.attrs['placeholder'] = f'Максимум: {remaining_quantity}'
            except Batch.DoesNotExist:
                self.fields['quantity'].widget.attrs['max'] = 0
                self.fields['quantity'].widget.attrs['placeholder'] = 'Партия не найдена'
    
    def clean(self):
        cleaned_data = super().clean()
        batch = cleaned_data.get('batch')
        quantity = cleaned_data.get('quantity')
        rack = cleaned_data.get('rack')
        
        if batch and quantity:
            # Проверяем, не превышает ли количество доступное для размещения
            remaining = batch.get_initial_remaining()
            if quantity > remaining:
                raise ValidationError(f'Нельзя разместить больше товара, чем осталось в партии. Доступно: {remaining}')
        
        if batch and rack and quantity:
            product = batch.product
            
            # Проверяем, поместится ли товар на стеллаж по габаритам
            if not rack.can_fit_product(product):
                raise ValidationError(f'Товар не помещается на выбранный стеллаж по габаритам')
            
            # Проверяем по весу
            if product.weight * quantity > rack.available_weight():
                raise ValidationError(f'Превышена допустимая нагрузка на стеллаж. Доступно: {rack.available_weight()} кг')
            
            # Проверяем по объему
            product_volume = product.get_volume() * quantity
            if product_volume > rack.available_volume():
                raise ValidationError(f'Недостаточно места на стеллаже. Доступно: {rack.available_volume()/1000:.2f} л')
        
        return cleaned_data

class IssueForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label='Товар')
    quantity = forms.IntegerField(min_value=1, label='Количество для выдачи')
    operator = forms.CharField(max_length=100, label='Кладовщик')
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity:
            # Проверка доступного количества товара на складе
            available_quantity = Placement.objects.filter(
                product=product, 
                is_active=True
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if quantity > available_quantity:
                raise ValidationError(f'Недостаточно товара на складе. Доступно: {available_quantity}')
        
        return cleaned_data

class CheckCapacityForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), label='Товар')
    quantity = forms.IntegerField(min_value=1, label='Планируемое количество')