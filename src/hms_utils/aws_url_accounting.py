# Script to get all possible URLs from all AWS accounts.
# TODO: Does not even include for example: wolf.smaht.org

import boto3
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import socket
import warnings
from hms_utils.aws_env import AwsProfiles

warnings.simplefilter('ignore', InsecureRequestWarning)


def _print(s):
    print(s, flush=True)


def list_elb_dns(account_id):
    session = boto3.Session(profile_name=account_id)
    elb_client = session.client('elbv2')
    response = elb_client.describe_load_balancers()
    elb_urls = []
    for lb in response['LoadBalancers']:
        dns = lb['DNSName']
        elb_urls.append(dns)
    return sorted(elb_urls)


def list_api_gateway_urls(account_id):
    session = boto3.Session(profile_name=account_id)
    api_gateway_client = session.client('apigateway')
    apis = api_gateway_client.get_rest_apis()
    api_urls = []
    for api in apis['items']:
        api_urls.append(f"{api['id']}.execute-api.{session.region_name}.amazonaws.com")
    return sorted(api_urls)


def list_cloudfront_urls(account_id):
    session = boto3.Session(profile_name=account_id)
    cloudfront_client = session.client('cloudfront')
    response = cloudfront_client.list_distributions()
    cf_urls = []
    if response := response['DistributionList']:
        for dist in response.get('Items', []):
            cf_urls.append(dist['DomainName'])
    return sorted(cf_urls)


def list_route53_urls(account_id):
    session = boto3.Session(profile_name=account_id)
    route53_client = session.client('route53')
    zones = route53_client.list_hosted_zones()
    all_urls = []
    for zone in zones['HostedZones']:
        records = route53_client.list_resource_record_sets(HostedZoneId=zone['Id'])
        for record in records['ResourceRecordSets']:
            if record['Type'] in ['A', 'CNAME']:
                if (dns := record['Name']).endswith("."):
                    dns = dns[:-1]
                all_urls.append(dns)
    return sorted(all_urls)


def resolve_cname(url):
    try:
        cname = socket.gethostbyname_ex(url)
        return cname[0] if cname else None
    except socket.gaierror:
        return None


def ping(dns):
    if dns.startswith("\\052."):
        return None, None, True
    if dns.endswith(".dev"):
        return None, None, True
    http = False
    https = False
    try:
        requests.get(f"http://{dns}", verify=False, timeout=4)
        http = True
    except Exception:
        pass
    try:
        requests.get(f"https://{dns}", verify=False, timeout=4)
        https = True
    except Exception:
        pass
    return http, https, False


def ping_suffix(dns):
    http, https, skip = ping(dns)
    if skip:
        return " (N/A)"
    if http:
        if https:
            return " (HTTP/HTTPS)"
        else:
            return " (HTTP)"
    elif https:
        return " (HTTPS)"
    else:
        return " (UNREACHABLE)"


aws_profiles = AwsProfiles.read()
for aws_profile in aws_profiles:
    _print(f"- ACCOUNT: {aws_profile.account} ({aws_profile.name})")
    if urls := list_elb_dns(aws_profile.name):
        _print(f"  - LOAD BALANCER: {len(urls)}")
        for url in urls:
            _print(f"    - {url}{ping_suffix(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {rurl}{ping_suffix(rurl)}")
    if urls := list_api_gateway_urls(aws_profile.name):
        _print(f"  - API GATEWAY: {len(urls)}")
        for url in urls:
            _print(f"    - {url}{ping_suffix(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {rurl}{ping_suffix(rurl)}")
    if urls := list_route53_urls(aws_profile.name):
        _print(f"  - ROUTE 53: {len(urls)}")
        for url in urls:
            _print(f"    - {url}{ping_suffix(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {rurl}{ping_suffix(rurl)}")
    if urls := list_cloudfront_urls(aws_profile.name):
        _print(f"  - CLOUD FRONT: {len(urls)}")
        for url in urls:
            _print(f"    - {url}{ping_suffix(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {rurl}{ping_suffix(rurl)}")
