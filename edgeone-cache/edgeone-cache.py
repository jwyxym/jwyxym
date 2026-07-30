import requests
import time
import hashlib
import hmac
import json
from datetime import datetime, timezone
import sys

TARGETS = json.loads(sys.argv[4])
TYPE = sys.argv[5]
METHOD = sys.argv[6]

API_ENDPOINT = "https://teo.tencentcloudapi.com"
API_HOST = "teo.tencentcloudapi.com"
API_SERVICE = "teo"
ACTION = "CreatePurgeTask"
VERSION = "2022-09-01"

SECRET_ID = sys.argv[1]
SECRET_KEY = sys.argv[2]
ZONE_ID = sys.argv[3]

def to_bytes(value):
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")


def sha256_hex(value):
    return hashlib.sha256(to_bytes(value)).hexdigest()


def hmac_sha256(key, value):
    return hmac.new(to_bytes(key), to_bytes(value), hashlib.sha256).digest()


def authorization(action, payload, timestamp, secret_id, secret_key):
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = "{}/{}/tc3_request".format(date, API_SERVICE)
    hashed_payload = sha256_hex(payload)
    canonical_headers = "\n".join([
        "content-type:application/json; charset=utf-8",
        "host:{}".format(API_HOST),
        "x-tc-action:{}".format(action.lower()),
    ]) + "\n"
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "\n".join([
        "POST",
        "/",
        "",
        canonical_headers,
        signed_headers,
        hashed_payload,
    ])
    hashed_canonical_request = sha256_hex(canonical_request)
    string_to_sign = "\n".join([
        algorithm,
        str(timestamp),
        credential_scope,
        hashed_canonical_request,
    ])

    secret_date = hmac_sha256("TC3{}".format(secret_key), date)
    secret_service = hmac_sha256(secret_date, API_SERVICE)
    secret_signing = hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, to_bytes(string_to_sign), hashlib.sha256).hexdigest()

    return (
        "{} Credential={}/{}, SignedHeaders={}, Signature={}".format(
            algorithm,
            secret_id,
            credential_scope,
            signed_headers,
            signature,
        )
    )

if __name__ == "__main__":
    timestamp = int(time.time())
    payload = json.dumps({
        "Type": TYPE,
        "Method": METHOD,
        "Targets": TARGETS,
        "ZoneId": ZONE_ID
    }, separators=(",", ":"))

    requests.post(
        API_ENDPOINT,
        headers={
            "Authorization": authorization(ACTION, payload, timestamp, SECRET_ID, SECRET_KEY),
            "Content-Type": "application/json; charset=utf-8",
            "Host": API_HOST,
            "X-TC-Action": ACTION,
            "X-TC-Version": VERSION,
            "X-TC-Timestamp": str(timestamp),
        },
        data=payload,
    )
