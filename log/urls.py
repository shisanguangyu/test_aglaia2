from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('log.views',
                       url(r'^show_log$', 'show_log'),
                       url(r'^show_purchase_destroy_list$', 'show_purchase_destroy_list')
                       )
