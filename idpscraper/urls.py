__author__ = 'Sebastian Hofstetter'

from django.conf.urls import url

from idpscraper import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^task/([^/]+)$', views.task, name='task'),
    url(r'^console$', views.console, name='console'),
    url(r'^relative_age$', views.relative_age, name='relative_age'),
    url(r'^export_task/([^.]+).txt', views.export_task, name='export_task'),
    url(r'^put_tasks', views.put_tasks, name='put_tasks'),
    url(r'^save_task/([^/]+)', views.save_task, name='save_task'),
    url(r'^delete_task/([^/]+)', views.delete_task, name='delete_task'),
    url(r'^delete_results/([^/]+)', views.delete_results, name='delete_results'),
    url(r'^test_task/([^/]+)', views.test_task, name='test_task'),
    url(r'^get_task/([^/]+)', views.get_task, name='get_task'),
    url(r'^test$', views.test, name='test'),
]