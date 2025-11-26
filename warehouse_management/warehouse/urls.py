from django.urls import path
from . import views

app_name = 'warehouse'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Товары
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    
    # Стеллажи
    path('racks/', views.RackListView.as_view(), name='rack_list'),
    path('racks/create/', views.RackCreateView.as_view(), name='rack_create'),
    path('racks/<int:pk>/update/', views.RackUpdateView.as_view(), name='rack_update'),
    
    # Партии
    path('batches/', views.BatchListView.as_view(), name='batch_list'),
    path('batches/create/', views.BatchCreateView.as_view(), name='batch_create'),
    path('batches/<int:batch_id>/suggest-racks/', views.SuggestRacksView.as_view(), name='suggest_racks'),
    path('batches/<int:batch_id>/place/', views.PlaceBatchView.as_view(), name='place_batch'),
    
    # Выдача товара
    path('issue/', views.IssueProductView.as_view(), name='issue_product'),
    
    # Поиск товара
    path('search/', views.SearchProductView.as_view(), name='search_product'),
    
    # Проверка вместимости
    path('check-capacity/', views.CheckCapacityView.as_view(), name='check_capacity'),
    
    # Журнал операций
    path('journal/', views.WarehouseJournalView.as_view(), name='journal'),
]