from Products.Archetypes.config import TOOL_NAME
from Products.CMFCore.utils import getToolByName
from bika.lims.utils import formatDecimalMark
from bika.lims.utils.analysis import format_numeric_result, get_significant_digits
from zExceptions import BadRequest
import json
import Missing
from pprint import pprint
from DateTime import DateTime

# Need to handle formatted result for DisplayResult 
# from metadata rather than indexing it directly
def handle_formattedDisplayResult(result, choices, threshold, precision, decimalmark='.', sciformat=1):
    """
    Returns a formatted result from an analysis using only catalog metadata

    :param result: result value of the analysis. Returned from Analysis catalog result.
    :param choices: ResultOptions dict of the analysis' service. Returned from Service catalog result.
    :param threshold: ExponentialFormatPrecision field of analysis' service. Returned from Service catalog result.
    :param precision: Precision field of analysis' service. Returned from Service catalog result.
    :param decimalmark: Uses default
    :param sciformat: Uses default

    Things it does not handle as of yet:
    1) hidemin/hidemax results
    2) multiple scientific notations, only uses default formatting
    3) uncertaintity in format precision
    """

    # Choices will be from catalog ResultOptions index

    # 1. Print ResultText of matching ResulOptions
    if choices is not None:
        match = [x['ResultText'] for x in choices
                 if str(x['ResultValue']) == str(result)]
        if match:
            return match[0]

    # 2. If the result is not floatable, return it without being formatted
    try:
        result = float(result)
    except:
        return result

    # Current result precision is above the threshold?
    sig_digits = get_significant_digits(float(result))
    negative = sig_digits < 0
    sign = '-' if negative else ''
    sig_digits = abs(sig_digits)
    sci = sig_digits >= float(threshold)

    formatted = ''
    if sci:
        # Default format: aE^+b
        formatted = str("%%.%se" % sig_digits) % result
    else:
        # Decimal notation
        prec = precision if precision else ''
        formatted = str("%%.%sf" % prec) % result
        formatted = str(int(float(formatted))) if float(formatted).is_integer() else formatted

    # Render numerical values
    return formatDecimalMark(formatted, decimalmark)

def handle_errors(f):
    """ simple JSON error handler
    """
    import traceback
    from plone.jsonapi.core.helpers import error

    def decorator(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception:
            var = traceback.format_exc()
            return error(var)

    return decorator


def get_include_fields(request, query="include_fields"):
    """Retrieve include_fields values from the request
    """
    include_fields = []
    rif = request.get(query, "")
    if query in request:
        include_fields = [x.strip()
                          for x in rif.split(",")
                          if x.strip()]
    if query+"[]" in request:
        include_fields = request[query+'[]']
    return include_fields


def load_brain_metadata(proxy, include_fields, catalog=None):
    """Load values from the catalog metadata into a list of dictionaries
    """
    ret = {}
    for index in proxy.indexes():
        if not index in proxy:
            continue
        if include_fields and index not in include_fields:
            continue
        val = getattr(proxy, index)

        if val != Missing.Value:
            try:
                # handle FieldIndexes that return metadat as DateTime objects
                if 'DateTime' in str(val.__class__):
                    val = str(val)

                json.dumps(val)
            except:
                continue
            ret[index] = val
        else:
            if catalog is not None:
                try:
                    val = catalog._catalog.getIndex(index).getEntryForObject(proxy.getRID(), default=None)
                    if val is None:
                        continue

                    # Parse certain index types as readable metadata
                    if 'BooleanIndex' in str(catalog._catalog.getIndex(index).__class__):
                        val = True if val else False
                    if 'DateIndex' in str(catalog._catalog.getIndex(index).__class__):
                        # Ignore dates since they use Zope timestamp conversion and not standard UTC timestamps
                        # TODO Should really make sure metadata works here instead
                        continue
                    if 'DateTime' in str(val.__class__):
                        val = str(val)

                    json.dumps(val)
                except:
                    continue
 
                ret[index] = val

    return ret


def load_field_values(instance, include_fields):
    """Load values from an AT object schema fields into a list of dictionaries
    """
    schema = instance.Schema()
    ret = {}
    for field in schema.fields():
        fieldname = field.getName()
        if include_fields and fieldname not in include_fields:
            continue
        val = field.get(instance)
        if val:
            if field.type == "blob":
                continue
            # I put the UID of all references here in *_uid.
            if field.type == 'reference':
                if type(val) in (list, tuple):
                    ret[fieldname + "_uid"] = [v.UID() for v in val]
                    val = [v.Title() for v in val]
                else:
                    ret[fieldname + "_uid"] = val.UID()
                    val = val.Title()
            if field.type == 'boolean':
                val = True if val else False
        try:
            json.dumps(val)
        except:
            val = str(val)
        ret[fieldname] = val
    return ret


def resolve_request_lookup(context, request, fieldname):
    if fieldname not in request:
        return []
    brains = []
    at = getToolByName(context, TOOL_NAME, None)
    entries = request[fieldname] if type(request[fieldname]) in (list, tuple) \
        else [request[fieldname], ]
    for entry in entries:
        contentFilter = {}
        for value in entry.split("|"):
            if ":" in value:
                index, value = value.split(":", 1)
            else:
                index, value = 'id', value
            if index in contentFilter:
                v = contentFilter[index]
                v = v if type(v) in (list, tuple) else [v, ]
                v.append(value)
                contentFilter[index] = v
            else:
                contentFilter[index] = value
        # search all possible catalogs
        if 'portal_type' in contentFilter:
            catalogs = at.getCatalogsByType(contentFilter['portal_type'])
        else:
            catalogs = [getToolByName(context, 'portal_catalog'), ]
        for catalog in catalogs:
            _brains = catalog(contentFilter)
            if _brains:
                brains.extend(_brains)
                break
    return brains


def set_fields_from_request(obj, request):
    """Search request for keys that match field names in obj,
    and call field mutator with request value.

    The list of fields for which schema mutators were found
    is returned.
    """
    schema = obj.Schema()
    # fields contains all schema-valid field values from the request.
    fields = {}
    for fieldname, value in request.items():
        if fieldname not in schema:
            continue
        if schema[fieldname].type in ('reference'):
            brains = []
            if value:
                brains = resolve_request_lookup(obj, request, fieldname)
                if not brains:
                    raise BadRequest("Can't resolve reference: %s" % fieldname)
            if schema[fieldname].multiValued:
                value = [b.UID for b in brains] if brains else []
            else:
                value = brains[0].UID if brains else None
        fields[fieldname] = value
    # Write fields.
    for fieldname, value in fields.items():
        field = schema[fieldname]
        fieldtype = field.getType()
        if fieldtype == 'Products.Archetypes.Field.BooleanField':
            if value.lower() in ('0', 'false', 'no') or not value:
                value = False
            else:
                value = True
        elif fieldtype in ['Products.ATExtensions.field.records.RecordsField',
                           'Products.ATExtensions.field.records.RecordField']:
            try:
                value = eval(value)
            except:
                raise BadRequest(fieldname + ": Invalid JSON/Python variable")
        mutator = field.getMutator(obj)
        if mutator:
            mutator(value)
        else:
            field.set(obj, value)
    obj.reindexObject()
    return fields.keys()
