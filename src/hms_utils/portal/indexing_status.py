import re
import requests
import sys
from hms_utils.chars import chars


def parse_database_count(value):
    match = re.search(r"DB:\s*(\d+)\s+ES:\s*(\d+)", value)
    if match:
        count = int(match.group(1))  # First captured group is the DB count
        return count
    return None


def parse_elasticsearch_count(value):
    match = re.search(r"DB:\s*(\d+)\s+ES:\s*(\d+)", value)
    if match:
        count = int(match.group(2))
        return count
    return None


def report_indexing_status_and_counts(name, domain, verbose):

    print()
    print(f"{chars.rarrow} {name}: {domain}")
    url = f"https://{domain}/indexing_status?format=json"
    response = requests.get(url)
    response = response.json()
    print(f"  {chars.rarrow_hollow} INDEX STATUS: {'' if response['status'] == 'Success' else response['status']}")
    print(f"    - Primary   waiting:   {response['primary_waiting']}")
    print(f"    - Primary   inflight:  {response['primary_inflight']}")
    print(f"    - Secondary waiting:   {response['secondary_waiting']}")
    print(f"    - Secondary inflight:  {response['secondary_inflight']}")
    print(f"    - DLQ       waiting:   {response['dlq_waiting']}")
    print(f"    - DLQ       inflight:  {response['dlq_inflight']}")

    url = f"https://{domain}/counts?format=json"
    response = requests.get(url)
    response = response.json()
    print(f"  {chars.rarrow_hollow} COUNTS:")
    database_elasticsearch_counts = response['db_es_total']
    database_count = parse_database_count(database_elasticsearch_counts)
    elasticsearch_count = parse_elasticsearch_count(database_elasticsearch_counts)
    if database_count > elasticsearch_count:
        database_suffix = f" {chars.rarrow_hollow} {database_count - elasticsearch_count} more"
        elasticsearch_suffix = ""
    elif elasticsearch_count > database_count:
        database_suffix = ""
        elasticsearch_suffix = f" {chars.rarrow_hollow} {elasticsearch_count - database_count} more"
    else:
        database_suffix = ""
        elasticsearch_suffix = ""
    print(f"    - Database:      {database_count}"
          f" {chars.check if database_count == elasticsearch_count else chars.xmark}{database_suffix}")
    print(f"    - ElasticSearch: {elasticsearch_count}"
          f" {chars.check if database_count == elasticsearch_count else chars.xmark}{elasticsearch_suffix}")
    if verbose and (database_count != elasticsearch_count):
        for item in response["db_es_compare"]:
            value = response["db_es_compare"][item]
            item_database_count = parse_database_count(value)
            item_elasticsearch_count = parse_elasticsearch_count(value)
            if item_database_count != item_elasticsearch_count:
                if database_count > elasticsearch_count:
                    database_suffix = f" {chars.rarrow_hollow} {database_count - elasticsearch_count} more"
                    elasticsearch_suffix = ""
                elif elasticsearch_count > database_count:
                    database_suffix = ""
                    elasticsearch_suffix = f" {chars.rarrow_hollow} {elasticsearch_count - database_count} more"
                else:
                    database_suffix = ""
                    elasticsearch_suffix = ""
                print(f"      {chars.rarrow_hollow} {item}:")
                print(f"        - Database:      {item_database_count}{database_suffix}")
                print(f"        - ElasticSearch: {item_elasticsearch_count}{elasticsearch_suffix}")


def main():

    smaht = False
    fourdn = False
    verbose = False

    if "smaht" in sys.argv:
        smaht = True
    if "4dn" in sys.argv:
        fourdn = True
    if not (("smaht" in sys.argv) or ("4dn" in sys.argv)):
        smaht = True
    if ("--verbose" in sys.argv) or ("-verbose" in sys.argv):
        verbose = True

    if smaht:
        report_indexing_status_and_counts("SMaHT STAGING", "staging.smaht.org", verbose)
        report_indexing_status_and_counts("SMaHT DATA", "data.smaht.org", verbose)

    if fourdn:
        report_indexing_status_and_counts("4DN STAGING", "staging.4dnucleome.org", verbose)
        report_indexing_status_and_counts("4DN DATA", "data.4dnucleome.org", verbose)

    print()


if __name__ == "__main__":
    main()
