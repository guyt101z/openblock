#   Copyright 2007,2008,2009,2011 Everyblock LLC, OpenPlans, and contributors
#
#   This file is part of ebpub
#
#   ebpub is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   ebpub is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with ebpub.  If not, see <http://www.gnu.org/licenses/>.
#

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from ebpub.constants import BLOCK_RADIUS_CHOICES
from ebpub.constants import BLOCK_RADIUS_DEFAULT
from ebpub.db.models import Location
from ebpub.db.models import Schema
from ebpub.streets.models import Block


def eb_render(request, *args, **kwargs):
    """
    Replacement for render_to_response that uses RequestContext.
    """
    kwargs['context_instance'] = RequestContext(request)
    return render_to_response(*args, **kwargs)

def parse_pid(pid):
    """
    Returns a tuple of (place, block_radius, xy_radius), where block_radius and
    xy_radius are None for Locations.

    PID examples:
        'b:12.1' (block ID 12, 1-block radius)
        'l:32' (location ID 32)
    """
    try:
        place_type, place_id = pid.split(':')
        if place_type == 'b':
            place_id, block_radius = place_id.split('.')
        place_id = int(place_id)
    except (KeyError, ValueError):
        raise Http404('Invalid place')
    if place_type == 'b':
        try:
            xy_radius = BLOCK_RADIUS_CHOICES[block_radius]
        except KeyError:
            raise Http404('Invalid radius')
        return (get_object_or_404(Block, id=place_id), block_radius, xy_radius)
    elif place_type == 'l':
        return (get_object_or_404(Location, id=place_id), None, None)
    else:
        raise Http404


def make_pid(place, block_radius=None):
    """
    Given a place (either a Location or Block), and an optional
    block_radius (None for Locations), returns a place ID string
    parseable by parse_pid.
    """
    if isinstance(place, Block):
        if block_radius is None:
            block_radius = BLOCK_RADIUS_DEFAULT
        block_radius = int(block_radius)
        return 'b:%d.%d' % (place.id, block_radius)
    elif isinstance(place, Location):
        assert block_radius is None
        return 'l:%d' % place.id
    else:
        raise ValueError("Wrong place type %s, expected Location or Block" % place)


def has_staff_cookie(request):
    return request.COOKIES.get(settings.STAFF_COOKIE_NAME) == settings.STAFF_COOKIE_VALUE

def get_schema_manager(request):
    """
    Returns a Manager that restricts the Schemas that can be seen
    based on the current request.

    This should be used in ALL public view queries that reference
    NewsItems or Schemas.  There should probably be a more convenient
    API for doing this.

    By default, this just uses ``has_staff_cookie`` to decide whether
    to show Schemas that are not public, but you can also name the
    path to a function in settings.SCHEMA_MANAGER_HOOK
    that has a signature like func(manager, request.user)
    and returns a manager.
    """
    if has_staff_cookie(request):
        manager = Schema.objects
    else:
        manager = Schema.public_objects
    return _manager_filter_hook(manager, request.user)

def get_schema_manager_for_user(user):
    """Like get_schema_manager(request),
    but useful in contexts where you have a User object available
    but no request, eg. batch jobs like sending email.

    This can also be overridden/enhanced by setting
    settings.SCHEMA_MANAGER_HOOK.
    """
    if user.is_superuser:
        manager = Schema.objects
    else:
        manager = Schema.public_objects
    return _manager_filter_hook(manager, user)

def _manager_filter_hook(manager, user):
    # Hook to customize the Manager's behavior based on the current user.
    # The named function should take (user, manager) arguments
    # and return something that behaves like a manager but can do whatever
    # extra filtering you like in eg. get_query_set().
    mgr_filter = getattr(settings, 'SCHEMA_MANAGER_HOOK', None)
    if mgr_filter is not None:
        module, func = mgr_filter.split(':')
        import importlib
        module = importlib.import_module(module)
        func = getattr(module, func)
        manager = func(user, manager)
    return manager
