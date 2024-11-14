from functools import lru_cache
import boto3
import sys
from typing import Optional, List
from hms_utils.dictionary_utils import sort_dictionary
from dcicutils.misc_utils import format_size
from dcicutils.portal_utils import Portal


@lru_cache(maxsize=1024)
def get_submission_center_info(submission_center_path: str) -> Optional[dict]:
    try:
        return portal.get(submission_center_path).json()
    except Exception:
        return {}


@lru_cache(maxsize=1024)
def get_submission_center_name(submission_center_path: str) -> str:
    return get_submission_center_info(submission_center_path).get("identifier", "")


def get_submission_centers(portal: Portal, submission_centers: List[dict]) -> List[str]:
    submission_center_names = []
    for submission_center in submission_centers:
        if submission_center_path := submission_center.get("@id"):
            if submission_center_name := get_submission_center_name(submission_center_path):
                if submission_center_name not in submission_center_names:
                    submission_center_names.append(submission_center_name)
    return submission_center_names


@lru_cache(maxsize=1024)
def get_submission_center_display_name(submission_center: str) -> str:
    try:
        return portal.get(f"/submission-centers/{submission_center}").json()["display_title"]
    except Exception:
        return ""


def get_file_size(file: dict) -> Optional[int]:
    if isinstance(file, dict) and (key := file.get("upload_key")) and (file.get("status") != "uploading"):
        bucket = "smaht-production-application-files"
        try:
            return boto3.client("s3").head_object(Bucket=bucket, Key=key)["ContentLength"]
        except Exception:
            pass
    return None


portal = Portal("smaht-data")
total = None ; limit = 220 ; offset = 0 ; nfiles_total = 0  # noqa

file_info_per_submission_center = {}

while True:
    url = f"/submitted-files?sort=uuid&from={offset}&limit={limit}"
    files = portal.get(url).json()
    files = files["@graph"]
    nfiles = len(files)
    for file in files:
        submission_centers = get_submission_centers(portal, file.get("submission_centers"))
        if (file_size := file.get("file_size")) is None:
            file_size = get_file_size(file)
        file_info = {
            "uuid": file.get("uuid"),
            "name": file.get("filename"),
            "size": file_size,
            "status": file.get("status"),
            "created": file.get("date_created"),
            "submission_centers": submission_centers
        }
        if not submission_centers:
            submission_center = None
        elif len(submission_centers) > 1:
            print(f"WARNING: More than one submission-center for submitted file:"
                  f" {file_info['name']} | {file_info['uuid']} | {', '.join(submission_centers)}",
                  file=sys.stderr, flush=True)
            submission_center = submission_centers[0]
        else:
            submission_center = submission_centers[0]
        if not (submission_center_file_info := file_info_per_submission_center.get(submission_center)):
            file_info_per_submission_center[submission_center] = [file_info]
        else:
            submission_center_file_info.append(file_info)
        print(f"Submitted Files: {nfiles_total}\r", end="", file=sys.stderr, flush=True)
        nfiles_total += 1
        if (total is not None) and (nfiles_total >= total):
            break
    if ((total is not None) and (nfiles_total >= total)) or (nfiles < limit):
        break
    offset += nfiles

file_summary_per_submission_center = {}
for submission_center in file_info_per_submission_center:
    total_files = 0 ; total_size = 0  # noqa
    for item in file_info_per_submission_center[submission_center]:
        total_files += 1
        total_size += (size if isinstance(size := item["size"], int) else 0)
    file_summary_per_submission_center[submission_center] = {"total_files": total_files, "total_size": total_size}
file_summary_per_submission_center = sort_dictionary(file_summary_per_submission_center)

print(f"Total submitted files and sizes by submission center:")
for submission_center in file_summary_per_submission_center:
    summary = file_summary_per_submission_center[submission_center]
    total_files = summary["total_files"]
    total_size = summary["total_size"]
    # print(f"{submission_center}: {total_files} | {format_size(total_size)}")
    print(f"{get_submission_center_display_name(submission_center)} ({submission_center}):")
    print(f"- Total Files: {total_files}")
    print(f"- Total Size: {format_size(total_size)} ({total_size})")

total_files = sum(item["total_files"] for item in file_summary_per_submission_center.values())
total_size = sum(item["total_size"] for item in file_summary_per_submission_center.values())
print("TOTAL:")
print(f"- Total Files: {total_files}")
print(f"- Total Size: {format_size(total_size)} ({total_size})")
