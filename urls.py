from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.contrib import admin
import hist_search.views

urlpatterns = [
    path(r'admin/', admin.site.urls),
    path(r'oauth/', include('social_django.urls', namespace='social')),
    path(r'', hist_search.views.index, name='home'),
    path(r'docs/', hist_search.views.docs, name='docs'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('search/', hist_search.views.search, name='search'),
]
