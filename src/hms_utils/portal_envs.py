import requests
import sys
from typing import Optional, Tuple
from dcicutils.captured_output import captured_output

ENVS = [
    {
        "name": "smaht-wolf",
        "url": "https://wolf.smaht.org"
    },
    {
        "name": "smaht-devtest",
        "url": "https://devtest.smaht.org"
    },
    {
        "name": "smaht-data",
        "url": "https://data.smaht.org",
        "blue_green": True
    },
    {
        "name": "smaht-staging",
        "url": "https://staging.smaht.org",
        "blue_green": True
    },
    {
        "name": "cgap-devtest",
        "url": "https://cgap-devtest.hms.harvard.edu",
        "defunct": True
    },
    {
        "name": "cgap-dbmi",
        "url": "https://cgap-dbmi.hms.harvard.edu"
    },
    {
        "name": "cgap-dfci",
        "url": "https://cgap-dfci.hms.harvard.edu",
        "defunct": True
    },
    {
        "name": "cgap-mgb",
        "url": "https://cgap-mgb.hms.harvard.edu"
    },
    {
        "name": "cgap-msa",
        "url": "https://cgap-msa.hms.harvard.edu"
    },
    {
        "name": "cgap-training",
        "url": "https://cgap-training.hms.harvard.edu"
    },
    {
        "name": "cgap-wolf",
        "url": "https://cgap-wolf.hms.harvard.edu"
    },
    {
        "name": "4dn-data",
        "url": "https://data.4dnucleome.org",
        "blue_green": True
    },
    {
        "name": "4dn-staging",
        "url": "https://staging.4dnucleome.org",
        "blue_green": True
    },
    {
        "name": "4dn-mastertest",
        "url": "https://mastertest.4dnucleome.org"
    },
    {
        "name": "4dn-hotseat",
        "url": "http://fourfront-hotseat-1650461284.us-east-1.elb.amazonaws.com"
    },
    {
        "name": "4dn-webdev",
        "url": "http://fourfront-webdev-1726959209.us-east-1.elb.amazonaws.com"
    }
]


def usage():
    print("usage: envs [--health] [pattern]")
    exit(1)


def main():

    env_pattern = None
    show_health = False
    health_key_pattern = None
    health_value_pattern = None

    argi = 0
    while argi < len(argv := sys.argv[1:]):
        arg = argv[argi]
        if (arg == "--health") or (arg == "-health") or (arg == "health"):
            show_health = True
        elif arg.startswith("--health:") or arg.startswith("--health:") or arg.startswith("health:"):
            health_key_pattern = arg[arg.find(":") + 1:]
        elif arg.startswith("--health/") or arg.startswith("--health/") or arg.startswith("health/"):
            health_value_pattern = arg[arg.find("/") + 1:]
        elif arg.startswith("-"):
            usage()
        else:
            env_pattern = arg
        argi += 1

    envs = [env for env in ENVS if env.get("defunct") is not True]
    if env_pattern:
        envs = [env for env in envs if env_pattern.lower() in env.get("name").lower()]
    for env in sorted(envs, key=lambda env: env.get("name")):
        name = env["name"]
        if url := env.get("url"):
            health, issue = get_health(url)
            if not health:
                print(f"{name}: Cannot connect: {url}")
                continue
            version = health.get("project_version")
            blue_green = None
            if env.get("blue_green"):
                if blue_green_identification := health.get("beanstalk_env", "").lower():
                    if "blue" in blue_green_identification:
                        blue_green = "blue"
                    elif "green" in blue_green_identification:
                        blue_green = "green"
            print(f"{chars.rarrow} {name}: {version}{f' ({blue_green})' if blue_green else ''}"
                  f"{f' ({issue})' if issue else ''}")
            if show_health or health_key_pattern or health_value_pattern:
                health = {key: health[key] for key in sorted(health)}
                for key in health:
                    if key.startswith("@"):
                        continue
                    if not isinstance(value := health[key], str):
                        value = str(value)
                    if health_key_pattern:
                        if health_key_pattern.lower() not in key.lower():
                            continue
                    if health_value_pattern:
                        if health_value_pattern.lower() not in value.lower():
                            continue
                    print(f"  - {key}: {value}")


def get_health(url: str) -> Tuple[Optional[dict], Optional[str]]:
    with captured_output(capture=True):
        try:
            if ((response := requests.get(f"{url}/health?format=json", verify=True)) and
                (response.status_code == 200) and
                (response := response.json())):  # noqa
                return response, None
        except Exception:
            if ((response := requests.get(f"{url}/health?format=json", verify=False)) and
                (response.status_code == 200) and
                (response := response.json())):  # noqa
                return response, "certificate issue"
            pass
    return None


class chars:
    check = "✓"
    xmark = "✗"
    rarrow = "▶"
    larrow = "◀"


if __name__ == "__main__":
    main()
