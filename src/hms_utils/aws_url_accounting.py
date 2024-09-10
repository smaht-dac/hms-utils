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
    apis = api_gateway_client.get_rest_apis(limit=1000)
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


def list_acm_certificates(account_id):
    session = boto3.Session(profile_name=account_id)
    client = session.client('acm')
    paginator = client.get_paginator('list_certificates')
    urls = []
    for page in paginator.paginate():
        for cert in page['CertificateSummaryList']:
            cert_arn = cert['CertificateArn']
            response = client.describe_certificate(CertificateArn=cert_arn)
            certificate = response['Certificate']
            domains = certificate['DomainName']
            subject_alternative_names = certificate.get('SubjectAlternativeNames', [])
            all_domains = [domains] + subject_alternative_names
            urls += all_domains
    return list(set(urls))


def resolve_cname(url):
    try:
        cname = socket.gethostbyname_ex(url)
        return cname[0] if cname else None
    except socket.gaierror:
        return None


def ping(dns):
    http = False
    https = False
    skip = False
    forbidden = False
    if dns.startswith("\\052."):
        skip = True
        return http, https, skip, forbidden
    elif dns.endswith(".dev"):
        skip = True
        return http, https, skip, forbidden
    elif dns.endswith(".app"):
        skip = True
        return http, https, skip, forbidden
    try:
        response = requests.get(f"http://{dns}", allow_redirects=False, verify=False, timeout=4)
        if response.status_code == 403:
            forbidden = True
        http = True
    except Exception:
        pass
    try:
        response = requests.get(f"https://{dns}", verify=False, timeout=4)
        if response.status_code == 403:
            forbidden = True
        https = True
    except Exception:
        pass
    return http, https, skip, forbidden


def redirect_url(dns):
    if dns.startswith("\\052."):
        return None
    elif dns.endswith(".dev"):
        return None
    elif dns.endswith(".app"):
        return None
    response = None
    try:
        response = requests.get(f"http://{dns}", allow_redirects=False, verify=False, timeout=4)
    except Exception:
        pass
    try:
        requests.get(f"https://{dns}", verify=False, timeout=4)
    except Exception:
        return None
    redirect_url = None
    if response and (response.status_code in [301, 302, 303, 307, 308]):
        if redirect_url := response.headers['location']:
            if redirect_url.endswith("/"):
                redirect_url = redirect_url[:-1]
            if redirect_url.endswith(":443"):
                redirect_url = redirect_url[:-4]
            if redirect_url.startswith("http://"):
                redirect_url = redirect_url[7:]
            elif redirect_url.startswith("https://"):
                redirect_url = redirect_url[8:]
            if redirect_url != dns:
                return redirect_url
    return redirect_url


def ping_suffix(dns):
    http, https, skip, forbidden = ping(dns)
    if skip:
        result = " (N/A)"
    if http:
        if https:
            result = " (HTTP/HTTPS)"
        else:
            result = " (HTTP)"
    elif https:
        result = " (HTTPS)"
    else:
        result = " (UNREACHABLE)"
    if forbidden:
        result += " (FORBIDDEN)"
    return result


def format_url(dns):
    http, https, skip, forbidden = ping(dns)
    result = ""
    if skip:
        result = f"{dns} (N/A)"
    if http:
        if https:
            result = f"https://{dns} (HTTP/HTTPS)"
        else:
            result = f"http://{dns} (HTTP)"
    elif https:
        result = f"https://{dns} (HTTPS)"
    else:
        result = f"{dns} (UNREACHABLE)"
    if forbidden:
        result += " (FORBIDDEN)"
    return result


def just_url(s):
    if index := s.find(" "):
        return s[0:index]
    return s


aws_profiles = AwsProfiles.read()
for aws_profile in aws_profiles:
    _print(f"- ACCOUNT: {aws_profile.account} ({aws_profile.name})")
    if urls := list_acm_certificates(aws_profile.name):
        _print(f"  - CERTIFICATES: {len(urls)}")
        for url in urls:
            _print(f"    - {format_url(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {format_url(rurl)}")
    if urls := list_elb_dns(aws_profile.name):
        _print(f"  - LOAD BALANCER: {len(urls)}")
        for url in urls:
            _print(f"    - {format_url(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {format_url(rurl)}")
            if (rurl := redirect_url(url)) and (rurl != url):
                _print(f"      - REDIRECT: {format_url(rurl)}")
    if urls := list_api_gateway_urls(aws_profile.name):
        _print(f"  - API GATEWAY: {len(urls)}")
        for url in urls:
            _print(f"    - {format_url(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {format_url(rurl)}")
    if urls := list_route53_urls(aws_profile.name):
        _print(f"  - ROUTE 53: {len(urls)}")
        for url in urls:
            _print(f"    - {format_url(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {format_url(rurl)}")
    if urls := list_cloudfront_urls(aws_profile.name):
        _print(f"  - CLOUD FRONT: {len(urls)}")
        for url in urls:
            _print(f"    - {format_url(url)}")
            if (rurl := resolve_cname(url)) and (rurl != url):
                _print(f"      - CNAME: {format_url(rurl)}")
