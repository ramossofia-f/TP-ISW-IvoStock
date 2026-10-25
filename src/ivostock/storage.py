import hashlib

import boto3
from botocore.exceptions import ClientError

from ivostock.config import Settings


class Snapshots:
    def __init__(self):
        cfg = Settings.from_env()
        self.bucket = cfg.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint,
            aws_access_key_id=cfg.s3_access_key,
            aws_secret_access_key=cfg.s3_secret_key,
            region_name="us-east-1",
        )

    def initialize(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        key = f"sha256/{digest}"
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=raw, IfNoneMatch="*")
        except ClientError as exc:
            if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                raise
        return key

    def get(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
