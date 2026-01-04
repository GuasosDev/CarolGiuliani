from core.views import GenericListView, GenericCreateView, GenericUpdateView, GenericDeleteView
from .models import Article

class ArticleListView(GenericListView):
    model = Article
    list_fields = ['code', 'description', 'price', 'stock']
    list_headers = ['Code', 'Description', 'Price', 'Stock']
    title = "Inventario de Artículos"
    create_url_name = 'article_create'
    update_url_name = 'article_update'
    delete_url_name = 'article_delete'

class ArticleCreateView(GenericCreateView):
    model = Article
    fields = ['code', 'description', 'price', 'stock']
    title = "Nuevo Artículo"
    # success_url_name removed as GenericCreateView handles success_url or HTMX response

class ArticleUpdateView(GenericUpdateView):
    model = Article
    fields = ['code', 'description', 'price', 'stock']
    title = "Editar Artículo"

class ArticleDeleteView(GenericDeleteView):
    model = Article
    title = "Eliminar Artículo"

