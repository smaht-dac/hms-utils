import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import Callable, List, Optional, Tuple, Union
from urllib.parse import urlencode
from dcicutils.datetime_utils import parse_datetime_string

AGGREGATION_FIELD_RELEASE_DATE = "file_status_tracking.released"
AGGREGATION_FIELD_CELL_LINE = "file_sets.libraries.analytes.samples.sample_sources.cell_line.code"
AGGREGATION_FIELD_DONOR = "donors.display_title"
AGGREGATION_FIELD_FILE_DESCRIPTOR = "release_tracker_description"

AGGREGATIONS = [
    AGGREGATION_FIELD_RELEASE_DATE,
    AGGREGATION_FIELD_CELL_LINE,
    AGGREGATION_FIELD_DONOR,
    AGGREGATION_FIELD_FILE_DESCRIPTOR
]

AGGREGATIONS_BY_CELL_LINE = [
    AGGREGATION_FIELD_RELEASE_DATE,
    AGGREGATION_FIELD_CELL_LINE,
    AGGREGATION_FIELD_FILE_DESCRIPTOR
]

AGGREGATIONS_BY_DONOR = [
    AGGREGATION_FIELD_RELEASE_DATE,
    AGGREGATION_FIELD_DONOR,
    AGGREGATION_FIELD_FILE_DESCRIPTOR
]

AGGREGATION_MAX_BUCKETS = 25
AGGREGATION_NO_VALUE = "No value"

DEFAULT_FILE_TYPES = ["OutputFile"]
DEFAULT_FILE_STATUSES = ["released"]
DEFAULT_FILE_CATEGORIES = ["!Quality Control"]
DEFAULT_RECENT_MONTHS = 3
DEFAULT_INCLUDE_CURRENT_MONTH = True


def create_query_for_files(
        type: Optional[Union[str, List[str]]] = None,
        status: Optional[Union[str, List[str]]] = None,
        category: Optional[Union[str, List[str]]] = None,
        from_date: Optional[str] = None,
        thru_date: Optional[str] = None,
        nmonths: Optional[str] = None,
        include_current_month: bool = False,
        date_property_name: Optional[str] = None,
        aggregation: Optional[Union[str, List[str], dict]] = None,
        max_buckets: Optional[int] = None,
        missing_value: Optional[str] = None) -> Tuple[Optional[str], Optional[dict]]:

    global AGGREGATION_FIELD_RELEASE_DATE

    types = []
    if type is None:
        type = DEFAULT_FILE_TYPES
    if not isinstance(type, list):
        type = [type]
    for item in type:
        if isinstance(item, str) and (item := item.strip()) and (item not in types):
            types.append(item)

    statuses = []
    if status is None:
        status = DEFAULT_FILE_STATUSES
    if not isinstance(status, list):
        status = [status]
    for item in status:
        if isinstance(item, str) and (item := item.strip()) and (item not in statuses):
            statuses.append(item)

    categories = []
    if category is None:
        category = DEFAULT_FILE_CATEGORIES
    if not isinstance(category, list):
        category = [category]
    for item in category:
        if isinstance(item, str) and (item := item.strip()) and (item not in categories):
            categories.append(item)

    from_date, thru_date = parse_date_related_arguments(from_date, thru_date, nmonths=nmonths,
                                                        include_current_month=include_current_month, strings=True)
    if from_date or thru_date:
        if not (isinstance(date_property_name, str) and (date_property_name := date_property_name.strip())):
            date_property_name = AGGREGATION_FIELD_RELEASE_DATE

    if not isinstance(aggregation, dict):
        aggregations = []
        if not isinstance(aggregation, list):
            aggregation = [aggregation]
        for item in aggregation:
            if isinstance(item, str) and (item := item.strip()) and (item not in aggregations):
                aggregations.append(item)
        def create_field_aggregation(field: str) -> Optional[dict]:  # noqa
            if field == AGGREGATION_FIELD_RELEASE_DATE:
                return {
                    "date_histogram": {
                        "field": f"embedded.{field}",
                        "calendar_interval": "month",
                        "format": "yyyy-MM",
                        "missing": "1970-01",
                        "order": {"_key": "desc"}
                    }
                }
        aggregation_definition = create_elasticsearch_aggregation_definitions(
            aggregations,
            max_buckets=max_buckets,
            missing_value=missing_value,
            create_field_aggregation=create_field_aggregation)
    else:
        aggregation_definition = aggregation

    query_parameters = {
        "type": types if types else None,
        "status": status if status else None,
        "data_category": categories if categories else None,
        f"{date_property_name}.from": from_date if from_date else None,
        f"{date_property_name}.to": thru_date if from_date else None,
        "from": 0,
        "limit": 0,

    }
    query_parameters = {key: value for key, value in query_parameters.items() if value is not None}

    query_string = urlencode(query_parameters, True)
    # Hackishness to change "=!" to "!=" in search_param_lists value for e.g.: "data_category": ["!Quality Control"]
    query_string = query_string.replace("=%21", "%21=")

    return query_string, aggregation_definition


def create_elasticsearch_aggregation_definitions(fields: List[str],
                                                 max_buckets: Optional[int] = None,
                                                 missing_value: Optional[str] = None,
                                                 create_field_aggregation: Optional[Callable] = None) -> dict:

    global AGGREGATION_MAX_BUCKETS, AGGREGATION_NO_VALUE

    if not (isinstance(fields, list) and fields and isinstance(field := fields[0], str) and field):
        return {}
    if not isinstance(missing_value, str):
        missing_value = AGGREGATION_NO_VALUE
    if not (isinstance(max_buckets, int) and (max_buckets > 0)):
        max_buckets = AGGREGATION_MAX_BUCKETS

    if not (callable(create_field_aggregation) and
            isinstance(field_aggregation := create_field_aggregation(field), dict)):
        field_aggregation = {
            "terms": {
                "field": f"embedded.{field}.raw",
                "missing": missing_value,
                "size": max_buckets
            }
        }

    aggregation = {field: field_aggregation}
    aggregation[field]["meta"] = {"field_name": field}

    if nested_aggregation := create_elasticsearch_aggregation_definitions(
            fields[1:], max_buckets=max_buckets,
            missing_value=missing_value,
            create_field_aggregation=create_field_aggregation):
        aggregation[field]["aggs"] = nested_aggregation

    return aggregation


def parse_date_related_arguments(
        from_date: Optional[Union[str, datetime, date]],
        thru_date: Optional[Union[str, datetime, date]],
        nmonths: Optional[Union[str, int]] = None,
        include_current_month: bool = True,
        strings: bool = False) -> Tuple[Optional[Union[str, datetime]], Optional[Union[str, datetime]]]:

    """
    Returns from/thru dates based on the given from/thru date arguments and optional nmonths argument.
    Given dates may be datetime or date objects or strings. Returned dates are datetime objects, or
    if the the given strings arguments is True, then strings (formatted as YYYY-MM-DD).

    If both of the given from/thru dates are specified/valid then those are returned
    and the given nmonths argument is not used.

    If only the given from date is specified then a None thru date is returned, UNLESS the given nmonths
    argument represents a positive integer, in which case the returned thru date will be nmonths months
    subsequent to the given from date; or if the given nmonths represents zero, in which case the
    returned thru date will be the last date of the month of the given from date.

    If only the given thru date is specified then a None from date is returned, UNLESS the given nmonths
    argument represents a negative integer, in which case the returned from date will be nmonths monthss
    previous to the given thru date; or if the given nmonths represents zero, in which case
    the returned from date will be the first date of the month of the given thru date.

    If neither the given from/thru dates are specified then None is returns for both, UNLESS the given
    nmonths arguments represents a non-zero integer, in which case the returned from/thru dates will represent
    the past (absolute value) nmonths months starting with the month previous to the month of "today"; however
    if the include_current_month is True it is rather the past nmonths starting with the month of "today".
    """
    from_date = _parse_datetime_string(from_date, notz=True)
    thru_date = _parse_datetime_string(thru_date, last_day_of_month_if_no_day=True, notz=True)
    if not isinstance(nmonths, int):
        if isinstance(nmonths, str) and (nmonths := nmonths.strip()):
            try:
                nmonths = int(nmonths)
            except Exception:
                nmonths = 0
        else:
            nmonths = 0
    if from_date:
        if (not thru_date) and isinstance(nmonths, int):
            if nmonths > 0:
                thru_date = add_months(from_date, nmonths)
            elif nmonths == 0:
                thru_date = get_last_date_of_month(from_date)
    elif thru_date:
        if isinstance(nmonths, int):
            if nmonths < 0:
                from_date = add_months(thru_date, nmonths)
            elif nmonths == 0:
                from_date = get_first_date_of_month(thru_date)
    elif isinstance(nmonths, int) and ((nmonths := abs(nmonths)) != 0):
        # If no (valid) from/thru dates given, but the absolute value of nmonths is a non-zero integer, then returns
        # from/thru dates for the last nmonths month ending with the last day of month previous to the current month.
        # thru_date = add_months(get_last_date_of_month(), -1)
        thru_date = get_last_date_of_month()
        if include_current_month is not True:
            thru_date = add_months(thru_date, -1)
        from_date = add_months(thru_date, -nmonths)
    if strings is True:
        return (from_date.strftime(f"%Y-%m-%d") if from_date else None,
                thru_date.strftime(f"%Y-%m-%d") if thru_date else None)
    return from_date, thru_date


def get_first_date_of_month(day: Optional[Union[datetime, date, str]] = None) -> datetime:
    """
    Returns a datetime object representing the first day of the month of the given date;
    this given date may be a datetime or date object, or string representing a date or
    datetime; if the given argument is unspecified or incorrect then assumes "today".
    """
    if not (day := _parse_datetime_string(day, notz=True)):
        day = datetime.today().replace(tzinfo=None)
    return day.replace(day=1)


def get_last_date_of_month(day: Optional[Union[datetime, date, str]] = None) -> datetime:
    """
    Returns a datetime object representing the last day of the month of the given date;
    this given date may be a datetime or date object, or string representing a date or
    datetime; if the given argument is unspecified or incorrect then assumes "today".
    """
    if not (day := _parse_datetime_string(day)):
        day = datetime.today().replace(tzinfo=None)
    return datetime(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def add_months(day: Optional[Union[datetime, date, str]] = None, nmonths: int = 0) -> datetime:
    """
    Returns a datetime object representing the given date with the given nmonths number of months
    added (or substracted if negative) to (or from) that given date.; this given date may be a
    datetime or date object, or string representing a date or datetime; if the given argument
    is unspecified or incorrect then assumes "today".
    """
    if not (day := _parse_datetime_string(day, notz=True)):
        day = datetime.today().replace(tzinfo=None)
    if isinstance(nmonths, int) and (nmonths != 0):
        return day + relativedelta(months=nmonths)
    return day


def _parse_datetime_string(value: Union[str, datetime, date],
                           last_day_of_month_if_no_day: bool = False,
                           notz: bool = False) -> Optional[datetime]:
    """
    Wrapper around dcicutils.datetime_utils.parse_datetime_string to handle a few special cases for convenience.
    """
    last_day_of_month = False
    if not isinstance(value, datetime):
        if isinstance(value, date):
            value = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            if (len(value) == 8) and value.isdigit():
                # Special case to accept for example "20241206" to mean "2024-12-06".
                value = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
            elif (len(value) == 7) and (value[4] == "-") and value[0:4].isdigit() and value[5:].isdigit():
                # Special case to accept for example "2024-10" to mean "2024-10-01".
                value = f"{value}-01"
                last_day_of_month = last_day_of_month_if_no_day
            elif (len(value) == 7) and (value[2] == "/") and value[0:2].isdigit() and value[3:].isdigit():
                # Special case to accept for example "11/2024" to mean "2024-11-01".
                value = f"{value[3:]}-{value[0:2]}-01"
                last_day_of_month = last_day_of_month_if_no_day
            elif (len(value) == 6) and (value[1] == "/") and value[0:1].isdigit() and value[2:].isdigit():
                # Special case to accept for example "9/2024" to mean "2024-09-01".
                value = f"{value[2:]}-0{value[0:1]}-01"
                last_day_of_month = last_day_of_month_if_no_day
            if not (value := parse_datetime_string(value)):
                return None
        else:
            return None
    value = value.replace(tzinfo=None) if notz is True else value
    if last_day_of_month:
        value = get_last_date_of_month(value)
    return value


import json  # noqa
import os  # noqa
from urllib.parse import unquote  # noqa
from hms_utils.dictionary_utils import get_property, group_items_by_groupings, normalize_elastic_search_aggregation_results  # noqa
from hms_utils.dictionary_print_utils import print_grouped_items  # noqa
from hms_utils.portal.portal_utils import Portal, portal_custom_search  # noqa

portal = Portal(os.path.expanduser("~/repos/smaht-portal/development.ini"))

if True:
    print(f"\nRECENT RELEASED FILES BY DATE & CELL-LINE & DONOR & FILE-DESCRIPTOR ...\n")
    query_string, aggregation_definition = create_query_for_files(type=DEFAULT_FILE_TYPES,
                                                                  status=DEFAULT_FILE_STATUSES,
                                                                  category=DEFAULT_FILE_CATEGORIES,
                                                                  nmonths=DEFAULT_RECENT_MONTHS,
                                                                  include_current_month=DEFAULT_INCLUDE_CURRENT_MONTH,
                                                                  date_property_name=AGGREGATION_FIELD_RELEASE_DATE,
                                                                  aggregation=AGGREGATIONS,
                                                                  max_buckets=AGGREGATION_MAX_BUCKETS,
                                                                  missing_value=AGGREGATION_NO_VALUE)
    result = portal_custom_search(portal, f"/search/?{query_string}", aggregations=aggregation_definition)
    result_aggregations = normalize_elastic_search_aggregation_results(result.get("aggregations"))
    print_grouped_items(result_aggregations)

if True:
    print(f"\nRECENT RELEASED FILES BY DATE & CELL-LINE & FILE-DESCRIPTOR ...\n")
    query_string, aggregation_definition = create_query_for_files(type=DEFAULT_FILE_TYPES,
                                                                  status=DEFAULT_FILE_STATUSES,
                                                                  category=DEFAULT_FILE_CATEGORIES,
                                                                  nmonths=DEFAULT_RECENT_MONTHS,
                                                                  include_current_month=DEFAULT_INCLUDE_CURRENT_MONTH,
                                                                  date_property_name=AGGREGATION_FIELD_RELEASE_DATE,
                                                                  aggregation=AGGREGATIONS_BY_CELL_LINE,
                                                                  max_buckets=AGGREGATION_MAX_BUCKETS,
                                                                  missing_value=AGGREGATION_NO_VALUE)
    result = portal_custom_search(portal, f"/search/?{query_string}", aggregations=aggregation_definition)
    result_aggregations = normalize_elastic_search_aggregation_results(result.get("aggregations"))
    print_grouped_items(result_aggregations)

if True:
    print(f"\nRECENT RELEASED FILES BY DATE & DONOR & FILE-DESCRIPTOR ...\n")
    query_string, aggregation_definition = create_query_for_files(type=DEFAULT_FILE_TYPES,
                                                                  status=DEFAULT_FILE_STATUSES,
                                                                  category=DEFAULT_FILE_CATEGORIES,
                                                                  nmonths=DEFAULT_RECENT_MONTHS,
                                                                  include_current_month=DEFAULT_INCLUDE_CURRENT_MONTH,
                                                                  date_property_name=AGGREGATION_FIELD_RELEASE_DATE,
                                                                  aggregation=AGGREGATIONS_BY_DONOR,
                                                                  max_buckets=AGGREGATION_MAX_BUCKETS,
                                                                  missing_value=AGGREGATION_NO_VALUE)
    result = portal_custom_search(portal, f"/search/?{query_string}", aggregations=aggregation_definition)
    result_aggregations = normalize_elastic_search_aggregation_results(result.get("aggregations"))
    print_grouped_items(result_aggregations)
