# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django import forms
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _

from .. import settings
from .permissions import PrimitivePermissionAwareModelAdmin
from ..models import File
from ..utils.compatibility import LTE_DJANGO_1_5, unquote
from .tools import popup_status, AdminContext, admin_url_params_encoded


class FileAdminChangeFrom(forms.ModelForm):
    class Meta(object):
        model = File
        exclude = ()


class FileAdmin(PrimitivePermissionAwareModelAdmin):
    list_display = ('label',)
    list_per_page = 10
    search_fields = ['name', 'original_filename', 'sha1', 'description']
    raw_id_fields = ('owner',)
    readonly_fields = ('sha1', 'display_canonical')

    # save_as hack, because without save_as it is impossible to hide the
    # save_and_add_another if save_as is False. To show only save_and_continue
    # and save in the submit row we need save_as=True and in
    # render_change_form() override add and change to False.
    save_as = True

    form = FileAdminChangeFrom

    def get_queryset(self, request):
        if LTE_DJANGO_1_5:
            return super(FileAdmin, self).queryset(request)
        return super(FileAdmin, self).get_queryset(request)

    @classmethod
    def build_fieldsets(cls, extra_main_fields=(), extra_advanced_fields=(),
                        extra_fieldsets=()):
        fieldsets = (
            (None, {
                'fields': (
                    'name',
                    'owner',
                    'description',
                ) + extra_main_fields,
            }),
            (_('Advanced'), {
                'fields': (
                    'file',
                    'sha1',
                    'display_canonical',
                ) + extra_advanced_fields,
                'classes': ('collapse',),
            }),
        ) + extra_fieldsets
        if settings.FILER_ENABLE_PERMISSIONS:
            fieldsets = fieldsets + (
                (None, {
                    'fields': ('is_public',)
                }),
            )
        return fieldsets

    def response_change(self, request, obj):
        """
        Overrides the default to be able to forward to the directory listing
        instead of the default change_list_view
        """
        admin_url_params = AdminContext(request)
        if (
            request.POST and
            admin_url_params.popup and
            admin_url_params.pick and
            '_continue' not in request.POST
        ):
            # popup in pick mode. response_change only gets called if the
            # operation was successful. In pick mode we just want to go
            # back to the folder list view and keep the params.
            if obj.folder:
                url = reverse('admin:filer-directory_listing',
                              kwargs={'folder_id': obj.folder.id})
            else:
                url = reverse(
                    'admin:filer-directory_listing-unfiled_images')
            url = "{0}{1}".format(
                url,
                admin_url_params_encoded(request),
            )
            return HttpResponseRedirect(url)
        return super(FileAdmin, self).response_change(request, obj)

    def render_change_form(self, request, context, add=False, change=False,
                           form_url='', obj=None):
        extra_context = {'show_delete': True,
                         'is_popup': popup_status(request),
                         'filer_admin_context': AdminContext(request)}
        context.update(extra_context)
        return super(FileAdmin, self).render_change_form(
            request=request, context=context, add=False, change=False,
            form_url=form_url, obj=obj)

    def delete_view(self, request, object_id, extra_context=None):
        """
        Overrides the default to enable redirecting to the directory view after
        deletion of a image.

        we need to fetch the object and find out who the parent is
        before super, because super will delete the object and make it
        impossible to find out the parent folder to redirect to.
        """
        try:
            obj = self.get_queryset(request).get(pk=unquote(object_id))
            parent_folder = obj.folder
        except self.model.DoesNotExist:
            parent_folder = None

        admin_url_params = AdminContext(request)
        if (
            request.POST and
            admin_url_params.popup and
            admin_url_params.pick
        ):
            # Popup in pick mode. Call super delete view so the objects
            # actually get deleted. All possible failures in delete_view cause
            # exceptions, so it is safe to ignore the return value though.
            super(FileAdmin, self).delete_view(
                request=request, object_id=object_id,
                extra_context=extra_context)
            if parent_folder:
                url = reverse('admin:filer-directory_listing',
                              kwargs={'folder_id': parent_folder.id})
            else:
                url = reverse('admin:filer-directory_listing-unfiled_images')
            url = "{0}{1}".format(
                url,
                admin_url_params_encoded(request)
            )
            return HttpResponseRedirect(url)

        return super(FileAdmin, self).delete_view(
            request=request, object_id=object_id,
            extra_context=extra_context)

    def get_model_perms(self, request):
        """
        It seems this is only used for the list view. NICE :-)
        """
        return {
            'add': False,
            'change': False,
            'delete': False,
        }

    def display_canonical(self, instance):
        canonical = instance.canonical_url
        if canonical:
            return '<a href="%s">%s</a>' % (canonical, canonical)
        else:
            return '-'
    display_canonical.allow_tags = True
    display_canonical.short_description = _('canonical URL')

FileAdmin.fieldsets = FileAdmin.build_fieldsets()
