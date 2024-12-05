import json
from copy import deepcopy
from typing import Any, List, Optional, Tuple
# from hms_utils.dictionary_utils import normalize_elastic_search_aggregation_results
from hms_utils.dictionary_print_utils import print_grouped_items  # noqa

def dj(value):
    import json
    print(json.dumps(value, indent=4, default=str))

# ❖ GROUP: file_status_tracking.released (2)
#   ▶ file_status_tracking.released:2024-11 (37)
#     ❖ GROUP: donors.display_title (4)
#       ▷ donors.display_title:DAC_DONOR_COLO829 (21)
#         ❖ GROUP: release_tracker_description (4)
#           ▷ release_tracker_description:WGS Illumina NovaSeq X bam (4)
#           ▷ release_tracker_description:Fiber-seq PacBio Revio bam (8)
#           ▷ release_tracker_description:WGS ONT PromethION 24 bam (2)
#           ▷ release_tracker_description:XXX WGS Illumina NovaSeq X bam (7)
#       ▷ donors.display_title:DAC_DONOR_COLO829_XYZZY (3)
#         ❖ GROUP: release_tracker_description (2)
#           ▷ release_tracker_description:WGS Illumina NovaSeq X bam (1)
#           ▷ release_tracker_description:Fiber-seq PacBio Revio bam (2)
#       ▷ file_sets.libraries.analytes.samples.sample_sources.cell_line.code:COLO829T (8)
#         ❖ GROUP: release_tracker_description (3)
#           ▷ release_tracker_description:WGS Illumina NovaSeq X bam (4)
#           ▷ release_tracker_description:Fiber-seq PacBio Revio bam (3)
#           ▷ release_tracker_description:WGS ONT PromethION 24 bam (1)
#       ▷ file_sets.libraries.analytes.samples.sample_sources.cell_line.code:COLO829BL (5)
#         ❖ GROUP: release_tracker_description (2)
#           ▷ release_tracker_description:WGS Illumina NovaSeq X bam (3)
#           ▷ release_tracker_description:Fiber-seq PacBio Revio bam (2)
#   ▶ file_status_tracking.released:2024-12 (15)
#     ❖ GROUP: donors.display_title (1)
#       ▷ donors.display_title:DAC_DONOR_COLO829 (15)
#         ❖ GROUP: release_tracker_description (3)
#           ▷ release_tracker_description:WGS Illumina NovaSeq X bam (8)
#           ▷ release_tracker_description:Fiber-seq PacBio Revio bam (5)
#           ▷ release_tracker_description:WGS ONT PromethION 24 bam (2)

group_by_donor = {
        "meta": { "field_name": "file_status_tracking.released" },
        "buckets": [
            {
                "key_as_string": "2024-11", "key": 1733011200000, "doc_count": 16,
                "donors.display_title": {
                    "meta": { "field_name": "donors.display_title" },
                    "buckets": [
                        {   "key": "DAC_DONOR_COLO829_XYZZY", "doc_count": 3,
                            "release_tracker_description": {
                                "meta": { "field_name": "release_tracker_description" },
                                "buckets": [
                                    { "key": "WGS Illumina NovaSeq X bam", "doc_count": 1 },
                                    { "key": "Fiber-seq PacBio Revio bam", "doc_count": 2 }
                                ]
                            }
                        },
                        {   "key": "DAC_DONOR_COLO829", "doc_count": 13,
                            "release_tracker_description": {
                                "meta": { "field_name": "release_tracker_description" },
                                "buckets": [
                                    { "key": "XXX WGS Illumina NovaSeq X bam", "doc_count": 7 },
                                    { "key": "Fiber-seq PacBio Revio bam", "doc_count": 5 },
                                    { "key": "WGS ONT PromethION 24 bam", "doc_count": 1 }
                                ]
                            }
                        }
                    ]
                }
            },
            {
                "key_as_string": "2024-12", "key": 1733011200000, "doc_count": 15,
                "donors.display_title": {
                    "meta": { "field_name": "donors.display_title" },
                    "buckets": [
                        {   "key": "DAC_DONOR_COLO829", "doc_count": 15,
                            "release_tracker_description": {
                                "meta": { "field_name": "release_tracker_description" },
                                "buckets": [
                                    { "key": "WGS Illumina NovaSeq X bam", "doc_count": 8 },
                                    { "key": "Fiber-seq PacBio Revio bam", "doc_count": 5 },
                                    { "key": "WGS ONT PromethION 24 bam", "doc_count": 2 }
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }

group_by_cell_line = {
        "meta": { "field_name": "file_status_tracking.released" },
        "buckets": [
            {
                "key_as_string": "2024-11", "key": 1733011200000, "doc_count": 21,
                "donors.display_title": {
                    "meta": { "field_name": "donors.display_title" },
                    "buckets": [
                        {    "key": "DAC_DONOR_COLO829", "doc_count": 8,
                            "release_tracker_description": {
                                "meta": { "field_name": "release_tracker_description" },
                                "buckets": [
                                    { "key": "WGS Illumina NovaSeq X bam", "doc_count": 4 },
                                    { "key": "Fiber-seq PacBio Revio bam", "doc_count": 3 },
                                    { "key": "WGS ONT PromethION 24 bam", "doc_count": 1 }
                                ]
                            }
                        }
                    ]
                },
                "file_sets.libraries.analytes.samples.sample_sources.cell_line.code": {
                    "meta": { "field_name": "file_sets.libraries.analytes.samples.sample_sources.cell_line.code" },
                    "buckets": [
                        {    "key": "COLO829T", "doc_count": 8,
                            "release_tracker_description": {
                                "meta": { "field_name": "release_tracker_description" },
                                "buckets": [
                                    { "key": "WGS Illumina NovaSeq X bam", "doc_count": 4 },
                                    { "key": "Fiber-seq PacBio Revio bam", "doc_count": 3 },
                                    { "key": "WGS ONT PromethION 24 bam", "doc_count": 1 }
                                ]
                            }
                        },
                        {    "key": "COLO829BL", "doc_count": 5,
                            "release_tracker_description": {
                                "meta": { "field_name": "release_tracker_description" },
                                "buckets": [
                                    { "key": "WGS Illumina NovaSeq X bam", "doc_count": 3 },
                                    { "key": "Fiber-seq PacBio Revio bam", "doc_count": 2 }
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }

def merge_elasticsearch_aggregations(target: dict, source: dict, copy: bool = False) -> Tuple[Optional[dict], Optional[int]]:

    def get_aggregation_key(aggregation: dict, aggregation_key: Optional[str] = None) -> Optional[str]:
        if isinstance(aggregation, dict) and isinstance(aggregation.get("buckets"), list):
            if isinstance(field_name := aggregation.get("meta", {}).get("field_name"), str) and field_name:
                if isinstance(aggregation_key, str) and aggregation_key:
                    if field_name != aggregation_key:
                        return None
                return field_name
        return None

    def get_nested_aggregation(aggregation: dict) -> Optional[dict]:
        if isinstance(aggregation, dict):
            for key in aggregation:
                if source_bucket_field := get_aggregation_key(aggregation[key], key):
                    return aggregation[key]
        return None

    def get_aggregation_bucket_value(aggregation_bucket: dict) -> Optional[Any]:
        if isinstance(aggregation_bucket, dict):
            return aggregation_bucket.get("key_as_string", aggregation_bucket.get("key"))
        return None

    def get_aggregation_bucket_doc_count(aggregation_bucket: dict) -> Optional[int]:
        if isinstance(aggregation_bucket, dict):
            if isinstance(doc_count := aggregation_bucket.get("doc_count"), int):
                return doc_count
        return None

    def find_aggregation_bucket(aggregation: dict, value: str) -> Optional[dict]:
        if get_aggregation_key(aggregation):
            for aggregation_bucket in aggregation["buckets"]: 
                if get_aggregation_bucket_value(aggregation_bucket) == value:
                    return aggregation_bucket
        return None

    if not ((aggregation_key := get_aggregation_key(source)) and (get_aggregation_key(target) == aggregation_key)):
        return None, None

    if copy is True:
        target = deepcopy(target)

    merged_item_count = 0

    for source_bucket in source["buckets"]:
        if (((source_bucket_value := get_aggregation_bucket_value(source_bucket)) is None) or
            ((source_bucket_item_count:= get_aggregation_bucket_doc_count(source_bucket)) is None)):
            continue
        if (target_bucket := find_aggregation_bucket(target, source_bucket_value)):
            if source_nested_aggregation := get_nested_aggregation(source_bucket):
                if target_nested_aggregation := get_nested_aggregation(target_bucket):
                    merged_item_count, _ = merge_elasticsearch_aggregations(target_nested_aggregation,
                                                                            source_nested_aggregation, copy=False)
                    if merged_item_count > 0:
                        target_bucket["doc_count"] += merged_item_count
            elif (target_bucket_value := get_aggregation_bucket_value(target_bucket)) is not None:
                if get_aggregation_bucket_doc_count(target_bucket) is not None:
                    target_bucket["doc_count"] += source_bucket_item_count
                    merged_item_count += source_bucket_item_count
            continue
        target["buckets"].append(source_bucket)
        merged_item_count += source_bucket_item_count

    return merged_item_count, target


def normalize_elastic_search_aggregation_results(data: dict, prefix_grouping_value: bool = False) -> dict:

    def get_items_with_buckets_list_property(data: dict) -> List[dict]:
        results = []
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], dict) and isinstance(data[key].get("buckets"), list):
                    results.append(data[key])
            if (not results) and data.get("buckets", list):
                results.append(data)
        return results

    def process_field(field: dict) -> None:
        if not (isinstance(field, dict) and isinstance(buckets := field.get("buckets"), list)):
            return
        group_items = {}
        item_count = 0
        for bucket in buckets:
            if (key := bucket.get("key_as_string", bucket.get("key"))) in ["No value", "null", "None"]:
                key = None
            if (prefix_grouping_value is True) and isinstance(key, str) and key:
                if (group_name := field.get("meta", {}).get("field_name")):
                    key = f"{group_name}:{key}"
            doc_count = bucket["doc_count"]
            item_count += doc_count
            if nested_fields := get_items_with_buckets_list_property(bucket):
                for nested_field in nested_fields:
                    if processed_field := process_field(nested_field):
                        if group_items.get(key):
                            group_items[key]["group_items"] = {**group_items[key]["group_items"],
                                                               **processed_field["group_items"]}
                            group_items[key]["item_count"] += processed_field["item_count"]
                            group_items[key]["group_count"] += processed_field["group_count"]
                        else:
                            group_items[key] = processed_field
                    else:
                        group_items[key] = doc_count

        return {
                # "group": group_name,
            "item_count": item_count,
            "group_count": len(group_items),
            "group_items": group_items,
        }

    if not isinstance(data, dict):
        return {}

    processed_fields = {}
    if items_with_buckets_list_property := get_items_with_buckets_list_property(data):
        for item_with_buckets_list_property in items_with_buckets_list_property:
            if processed_field := process_field(item_with_buckets_list_property):
                if processed_fields:
                    # Here just for completeness; in practice no multiple groupings at top-level.
                    processed_fields["group_items"] = {**processed_fields["group_items"], **processed_field["group_items"]}
                else:
                    processed_fields = processed_field
        return processed_fields

merge_elasticsearch_aggregations(group_by_cell_line, group_by_donor)
dj(group_by_cell_line)
x = normalize_elastic_search_aggregation_results(group_by_cell_line, prefix_grouping_value=True)
dj(x)
import pdb ; pdb.set_trace()  # noqa
print_grouped_items(x)
