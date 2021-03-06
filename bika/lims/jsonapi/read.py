from Products.CMFPlone.utils import safe_unicode
from bika.lims import logger, to_utf8
from bika.lims.interfaces import IJSONReadExtender
from bika.lims.jsonapi import get_include_fields, handle_formattedDisplayResult
from plone.jsonapi.core import router
from plone.jsonapi.core.interfaces import IRouteProvider
from plone.protect.authenticator import AuthenticatorView
from bika.lims.jsonapi import load_brain_metadata
from bika.lims.jsonapi import load_field_values
from Products.CMFCore.utils import getToolByName
from zope import interface
from zope.component import getAdapters
import re
import App
from pprint import pprint


def read(context, request):
    tag = AuthenticatorView(context, request).authenticator()
    pattern = '<input .*name="(\w+)".*value="(\w+)"'
    _authenticator = re.match(pattern, tag).groups()[1]

    ret = {
        "url": router.url_for("read", force_external=True),
        "success": True,
        "error": False,
        "objects": [],
        "_authenticator": _authenticator,
    }
    debug_mode = App.config.getConfiguration().debug_mode
    catalog_name = request.get("catalog_name", "portal_catalog")
    if not catalog_name:
        raise ValueError("bad or missing catalog_name: " + catalog_name)
    catalog = getToolByName(context, catalog_name)
    indexes = catalog.indexes()

    # Bika setup cataolog for services
    bsc = getToolByName(context, 'bika_setup_catalog')

    def formatFilter (filterValue):
      if filterValue == 'true':
          return True
      elif filterValue == 'false':
          return False
      else:
          return safe_unicode(filterValue)

    contentFilter = {}
    for index in indexes:
        if index in request:
            if index == 'review_state' and "{" in request[index]:
                continue
            contentFilter[index] = formatFilter(request[index])
        if "%s[]"%index in request:
            value = request["%s[]"%index]
            contentFilter[index] = [formatFilter(v) for v in value]

    if 'limit' in request:
        try:
            contentFilter['sort_limit'] = int(request["limit"])
        except ValueError:
            pass
    sort_on = request.get('sort_on', 'id')
    contentFilter['sort_on'] = sort_on
    # sort order
    sort_order = request.get('sort_order', '')
    if sort_order:
        contentFilter['sort_order'] = sort_order
    else:
        sort_order = 'ascending'
        contentFilter['sort_order'] = 'ascending'

    include_fields = get_include_fields(request)
    if debug_mode:
        logger.info("contentFilter: " + str(contentFilter))

    # Get matching objects from catalog
    proxies = catalog(**contentFilter)

    subContentFilter = {}
    handleDisplayResult = False
    if 'include_sub' in request:
        subContentFilter['portal_type'] = request['include_sub']
        if 'sub_catalog' in request:
            sub_catalog = getToolByName(context, request['sub_catalog'])
        else:
            sub_catalog = catalog

        if 'DisplayResult' in request['sub_include_fields'].split(','):
            handleDisplayResult = True

    if 'DisplayResult' in include_fields:
        handleDisplayResult = True

    # batching items
    page_nr = int(request.get("page_nr", 0))
    try:
        page_size = int(request.get("page_size", 10))
    except ValueError:
        page_size = 10
    # page_size == 0: show all
    if page_size == 0:
        page_size = len(proxies)
    first_item_nr = page_size * page_nr
    if first_item_nr > len(proxies):
        first_item_nr = 0
    page_proxies = proxies[first_item_nr:first_item_nr + page_size]
    for proxy in page_proxies:
        obj_data = {}

        # Place all proxy attributes into the result.
        obj_data.update(load_brain_metadata(proxy, include_fields, catalog))

        if 'metadata_only' in request and not 'include_sub' in request:
            if handleDisplayResult:
                if 'ResultOptions' in obj_data:
                    choices = obj_data['ResultOptions']
                else:
                    choices = None

                service = bsc({'UID': obj_data['ServiceUID']})
                threshold = bsc._catalog.getIndex('getExponentialFormatPrecision').getEntryForObject(service[0].getRID(), default=None)
                precision = bsc._catalog.getIndex('getPrecision').getEntryForObject(service[0].getRID(), default=None)
                obj_data['DisplayResult'] = handle_formattedDisplayResult(obj_data['Result'], choices, threshold, precision)



        if 'include_sub' in request and 'metadata_only' in request:
            obj_data.update({request['include_sub']:[]})
            # subContentFilter['RequestUID'] = proxy['UID']
            path = catalog._catalog.getIndex('path').getEntryForObject(proxy.getRID(), default=None)
            subContentFilter['path'] = {'query': path, 'depth': 1}
            sub_proxies = sub_catalog(**subContentFilter)
            
            for proxy in sub_proxies:
                obj_data[request['include_sub']].append(load_brain_metadata(proxy, get_include_fields(request, query="sub_include_fields"), sub_catalog))
                if handleDisplayResult:

                    # iterate all ananlyses in the AR and update DisplayResult
                    for i, child in enumerate(obj_data[request['include_sub']]):
                        if 'ResultOptions' in obj_data[request['include_sub']][i]:
                            choices = obj_data[request['include_sub']][i]['ResultOptions']
                        else:
                            choices = None

                        service = bsc({'UID': obj_data[request['include_sub']][i]['ServiceUID']})
                        threshold = bsc._catalog.getIndex('getExponentialFormatPrecision').getEntryForObject(service[0].getRID(), default=None)
                        precision = bsc._catalog.getIndex('getPrecision').getEntryForObject(service[0].getRID(), default=None)
                        obj_data[request['include_sub']][i]['DisplayResult'] = handle_formattedDisplayResult(obj_data[request['include_sub']][i]['Result'], choices, threshold, precision)


        # Place all schema fields ino the result only if not metadata-only request.
        if not 'metadata_only' in request:
            obj = proxy.getObject()
            obj_data.update(load_field_values(obj, include_fields))

            obj_data['path'] = "/".join(obj.getPhysicalPath())

            # call any adapters that care to modify this data.
            adapters = getAdapters((obj, ), IJSONReadExtender)
            for name, adapter in adapters:
                adapter(request, obj_data)

        ret['objects'].append(obj_data)

    ret['total_objects'] = len(proxies)
    ret['first_object_nr'] = first_item_nr
    last_object_nr = first_item_nr + len(page_proxies)
    if last_object_nr > ret['total_objects']:
        last_object_nr = ret['total_objects']
    ret['last_object_nr'] = last_object_nr

    if debug_mode:
        logger.info("{0} objects returned".format(len(ret['objects'])))
    return ret


class Read(object):
    interface.implements(IRouteProvider)

    def initialize(self, context, request):
        pass

    @property
    def routes(self):
        return (
            ("/read", "read", self.read, dict(methods=['GET', 'POST'])),
        )

    def read(self, context, request):
        """/@@API/read: Search the catalog and return data for all objects found

        Optional parameters:

            - catalog_name: uses portal_catalog if unspecified
            - limit  default=1
            - All catalog indexes are searched for in the request.

        {
            runtime: Function running time.
            error: true or string(message) if error. false if no error.
            success: true or string(message) if success. false if no success.
            objects: list of dictionaries, containing catalog metadata
        }
        """

        return read(context, request)
