import pyramid
from typing import List, Optional
from urllib.parse import urlencode
from encoded.root import SMAHTRoot
from encoded.elasticsearch_utils import (
    create_elasticsearch_aggregation_query,
    merge_elasticsearch_aggregation_results,
    normalize_elasticsearch_aggregation_results)
from encoded.endpoint_utils import parse_date_range_related_arguments
from encoded.endpoint_utils import request_arg, request_args, request_arg_bool, request_arg_int

from snovault.search.search import search as snovault_search
from snovault.search.search_utils import make_search_subreq as snovault_make_search_subreq

from hms_utils.misc_utils import dj
from hms_utils.chars import chars
from hms_utils.terminal_utils import terminal_color

QUERY_FILE_TYPES = ["OutputFile"]
QUERY_FILE_STATUSES = ["released"]
QUERY_FILE_CATEGORIES = ["!Quality Control"]
QUERY_RECENT_MONTHS = 3
QUERY_INCLUDE_CURRENT_MONTH = True

AGGREGATION_FIELD_RELEASE_DATE = "file_status_tracking.released"
AGGREGATION_FIELD_CELL_LINE = "file_sets.libraries.analytes.samples.sample_sources.cell_line.code"
AGGREGATION_FIELD_DONOR = "donors.display_title"
AGGREGATION_FIELD_FILE_DESCRIPTOR = "release_tracker_description"

AGGREGATION_MAX_BUCKETS = 100
AGGREGATION_NO_VALUE = "No value"

import os
from encoded.recent_files_summary import recent_files_summary
from hms_utils.dictionary_print_utils import print_grouped_items
from hms_utils.portal.portal_utils import create_pyramid_request_for_testing, portal_custom_search, Portal

def test():

    request_args = {
        "nmonths": 18,
        "include_current_month": "true",
        # "date_property_name": "date_created",
        "nocells": True,  # TODO: PROBABLY MAKE THIS THE DEFAULT (PER ELIZABETH SUGGESTION 2024-12-11) 
        # "legacy": True,
        # "nomixtures": True,
        # "favor_donor": True,
        "troubleshoot": True,
        "troubleshoot_elasticsearch": True,
        "debug": False,
        "debug_query": False,
        "include_missing": False,
        "raw": False,
        # "willrfix": True,
    }

    portal = Portal(os.path.expanduser("~/repos/smaht-portal/development.ini"))

    def request_embed(query: str, as_user: Optional[str] = None) -> Optional[dict]:
        nonlocal portal
        return portal.get_metadata(query)

    request = create_pyramid_request_for_testing(portal.vapp, request_args)
    request.embed = request_embed

    results = recent_files_summary(request)

    # print("FINAL RESULTS:")
    # dj(results)
    print_normalized_aggregation_results(results, uuids=True, uuid_details=True, verbose=False)


def print_normalized_aggregation_results(data: dict,
                                         title: Optional[str] = None,
                                         parent_grouping_name: Optional[str] = None,
                                         parent_grouping_value: Optional[str] = None,
                                         uuids: bool = False,
                                         uuid_details: bool = False,
                                         verbose: bool = False,
                                         indent: int = 0) -> None:

    sample_source_property_name = "file_sets.libraries.analytes.samples.sample_sources.code"
    cell_line_property_name = "file_sets.libraries.analytes.samples.sample_sources.cell_line.code"
    donor_property_name = "donors.display_title"
    red = lambda text: terminal_color(text, "red")
    green = lambda text: terminal_color(text, "green")
    bold = lambda text: terminal_color(text, "white", bold=True)

    def format_hit_property_values(hit: dict, property_name: str) -> Optional[str]:
        nonlocal parent_grouping_name, parent_grouping_value
        if property_value := hit.get(property_name):
            if property_name == parent_grouping_name:
                property_values = []
                for property_value in property_value.split(","):
                    if (property_value := property_value.strip()) == parent_grouping_value:
                        property_values.append(green(property_value))
                    else:
                        property_values.append(property_value)
                property_value = ", ".join(property_values)
        return property_value

    def get_hits(data: dict) -> List[str]:
        hits = []
        if isinstance(portal_hits := data.get("debug", {}).get("portal_hits"), list):
            for portal_hit in portal_hits:
                if isinstance(portal_hit, dict) and isinstance(uuid := portal_hit.get("uuid"), str) and uuid:
                    hits.append(portal_hit)
        return hits

    if not (isinstance(data, dict) and data):
        return
    if not (isinstance(indent, int) and (indent > 0)):
        indent = 0
    spaces = (" " * indent) if indent > 0 else ""
    grouping_name = data.get("name")
    if isinstance(grouping_value := data.get("value"), str) and grouping_value:
        grouping = grouping_value
        if (verbose is True) and isinstance(grouping_name, str) and grouping_name:
            grouping = f"{grouping_name} {chars.dot} {grouping}"
    elif not (isinstance(grouping := title, str) and  grouping):
        grouping = "RESULTS"
    grouping = f"{chars.diamond} {bold(grouping)}"
    hits = get_hits(data) if (uuids is True) else []
    if isinstance(count := data.get("count"), int):
        note = ""
        if len(hits) > count:
            note = red(f" {chars.rarrow_hollow} more actual results: {len(hits) - count}")
        print(f"{spaces}{grouping}: {count}{note}")
    for hit in hits:
        if isinstance(hit, dict) and isinstance(uuid := hit.get("uuid"), str) and uuid:
            note = ""
            if hit.get("elasticsearch_counted") is False:
                note = red(f" {chars.xmark} not counted")
            else:
                note = f" {chars.check}"
            print(f"{spaces}  {chars.dot} {uuid}{note}")
            if uuid_details is True:
                if sample_sources := format_hit_property_values(hit, sample_source_property_name):
                    print(f"{spaces}    {chars.dot_hollow} sample-sources: {sample_sources}")
                if cell_lines := format_hit_property_values(hit, cell_line_property_name):
                    print(f"{spaces}    {chars.dot_hollow} cell-lines: {cell_lines}")
                if donors := format_hit_property_values(hit, donor_property_name):
                    print(f"{spaces}    {chars.dot_hollow} donors: {donors}")
    if isinstance(items := data.get("items"), list):
        for element in items:
            print_normalized_aggregation_results(element,
                                                 parent_grouping_name=grouping_name,
                                                 parent_grouping_value=grouping_value,
                                                 uuids=uuids, uuid_details=uuid_details,
                                                 verbose=verbose, indent=indent+2)

test()


"""
GROUPED BY CELL-LINE:

❖ GROUP: date_created (3)
  ▶ 2024-12 (20)
    ❖ GROUP: file_sets.libraries.analytes.samples.sample_sources.cell_line.code (9)
      ▷ ∅ (2)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (2)
            • 1a5b9cea-104e-45f3-9bef-8ed06aeede24 • 2024-12-07 • ST003
            • c53931bc-e3dc-4a37-97f3-05ffa2dc438b • 2024-12-07 • ST004
      ▷ COLO829T (7)
        ❖ GROUP: release_tracker_description (3)
          ▷ WGS ONT PromethION 24 bam (1)
            • 03ae4878-4fe0-4730-934a-abf211ccf77e • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
          ▷ WGS Illumina NovaSeq X bam (4)
            • ea0f5f17-5753-42ed-b141-186e8261c58e • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • f9cc4a7a-9508-441b-91f2-99530f8c82c7 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • fffceff8-4283-485d-b7ab-0cc19d3d1fa7 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • f5d1c1f5-febe-401b-aeea-a8da8de1ba32 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
          ▷ Fiber-seq PacBio Revio bam (2)
            • ccfc6527-ccdc-4e16-9df9-fb9c1eaf38b5 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • 2578886d-e809-414b-a328-acdf699821b0 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
      ▷ HG00438 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG02486 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG02622 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG005 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG02257 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG002 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ COLO829BL (5)
        ❖ GROUP: release_tracker_description (2)
          ▷ Fiber-seq PacBio Revio bam (2)
            • 3dccda14-8b17-4157-b3e6-4d9f1fafda5f • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • bdfb8964-1102-4baa-bd54-52b2feda4b03 • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
          ▷ WGS Illumina NovaSeq X bam (3)
            • 4cd1dff1-ceda-48c7-824e-26c43906083a • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • d8d46859-7e93-46fa-aaf7-8427177a14fb • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • dd8926f1-a560-4a7b-ae43-00d95b48b11e • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
  ▶ 2024-11 (1)
    ❖ GROUP: file_sets.libraries.analytes.samples.sample_sources.cell_line.code (1)
      ▷ COLO829T (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ Fiber-seq PacBio Revio bam (1)
            • 2bde1fae-13af-4086-ba25-edba2594c732 • 2024-11-07 • COLO829T • DAC_DONOR_COLO829
  ▶ 2024-10 (6)
    ❖ GROUP: file_sets.libraries.analytes.samples.sample_sources.cell_line.code (6)
      ▷ HG00438 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG02486 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG02622 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG005 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG02257 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ HG002 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002

GROUPED BY DONOR:

❖ GROUP: date_created (3)
  ▶ 2024-12 (15)
    ❖ GROUP: donors.display_title (4)
      ▷ ∅ (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • dbba7681-88ea-4a09-884d-ff64cc6c557a • 2024-12-07 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
      ▷ DAC_DONOR_COLO829 (12)
        ❖ GROUP: release_tracker_description (3)
          ▷ WGS ONT PromethION 24 bam (1)
            • 03ae4878-4fe0-4730-934a-abf211ccf77e • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
          ▷ WGS Illumina NovaSeq X bam (7)
            • ea0f5f17-5753-42ed-b141-186e8261c58e • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • f9cc4a7a-9508-441b-91f2-99530f8c82c7 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • 4cd1dff1-ceda-48c7-824e-26c43906083a • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • fffceff8-4283-485d-b7ab-0cc19d3d1fa7 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • d8d46859-7e93-46fa-aaf7-8427177a14fb • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • f5d1c1f5-febe-401b-aeea-a8da8de1ba32 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • dd8926f1-a560-4a7b-ae43-00d95b48b11e • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
          ▷ Fiber-seq PacBio Revio bam (4)
            • 3dccda14-8b17-4157-b3e6-4d9f1fafda5f • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • bdfb8964-1102-4baa-bd54-52b2feda4b03 • 2024-12-07 • COLO829BL • DAC_DONOR_COLO829
            • ccfc6527-ccdc-4e16-9df9-fb9c1eaf38b5 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
            • 2578886d-e809-414b-a328-acdf699821b0 • 2024-12-07 • COLO829T • DAC_DONOR_COLO829
      ▷ ST003 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • 1a5b9cea-104e-45f3-9bef-8ed06aeede24 • 2024-12-07 • ST003
      ▷ ST004 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS Illumina NovaSeq X bam (1)
            • c53931bc-e3dc-4a37-97f3-05ffa2dc438b • 2024-12-07 • ST004
  ▶ 2024-11 (1)
    ❖ GROUP: donors.display_title (1)
      ▷ DAC_DONOR_COLO829 (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ Fiber-seq PacBio Revio bam (1)
            • 2bde1fae-13af-4086-ba25-edba2594c732 • 2024-11-07 • COLO829T • DAC_DONOR_COLO829
  ▶ 2024-10 (1)
    ❖ GROUP: donors.display_title (1)
      ▷ ∅ (1)
        ❖ GROUP: release_tracker_description (1)
          ▷ WGS ONT PromethION 24 bam (1)
            • f2584000-f810-44b6-8eb7-855298c58eb3 • 2024-10-16 • HG00438, HG02486, HG02622, HG005, HG02257, HG002
"""
