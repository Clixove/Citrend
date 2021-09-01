"""citrend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
import my_login.views as v1
import task_manager.views as v2
import payment.views as v3
import task_runtime.views as v4

urlpatterns = [
    path('admin/', admin.site.urls),
    # my login
    path('my_login/view', v1.view_login),
    path('my_login/add', v1.add_login),
    path('my_login/delete', v1.delete_login),
    path('my_login/register', v1.view_register),
    path('my_login/register/add', v1.add_register),
    path('my_login/register/confirm/<str:invitation_code>', v1.add_user),
    # payment - donation
    path('payment/donate', v3.donate),
    path('payment/method/<int:idx>', v3.view_method),
    path('payment/transaction', v3.view_transaction),
    path('payment/add', v3.add_transaction),
    path('payment/prestige', v3.view_prestige),
    path('payment/prestige/add/<str:token>', v3.view_add_prestige),
    path('payment/prestige/add', v3.add_prestige),
    path('payment/subscription', v3.view_add_subscription),
    path('payment/subscription/add-1', v3.add_subscription_1),
    path('payment/subscription/add-2', v3.add_subscription_2),
    # task manager
    path('main', v2.view_main),
    path('factory/view-add-1', v2.view_create_factory),
    path('factory/add-1', v2.create_factory),
    path('factory/<int:idx>/view-add-2', v2.view_assign_sheet),
    path('factory/add-2', v2.assign_sheet),
    path('factory/<int:idx>/view-add-3', v2.view_assign_column),
    path('factory/add-3', v2.assign_column),
    path('factory/<int:idx>/view-add-4', v2.view_config_model),
    path('factory/add-4', v2.config_model),
    path('factory/<int:idx>/delete', v2.delete_factory),
    # task runtime
    path('runtime/view_train/<int:idx>', v4.view_train),
    path('runtime/train/<int:idx>/<int:processed>', v4.train),
    path('runtime/view_predict/<int:idx>', v4.view_predict),
    path('runtime/add_predict', v4.add_predict),
    path('runtime/file/<int:idx>', v4.view_prediction_results),
    path('runtime/predict', v4.predict),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
