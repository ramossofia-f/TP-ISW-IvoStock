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
            region_name=cfg.s3_region,
        )
        self.region = cfg.s3_region

    def initialize(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
            # Fuera de us-east-1, S3 exige declarar la región del bucket al crearlo.
            extra = (
                {}
                if self.region == "us-east-1"
                else {"CreateBucketConfiguration": {"LocationConstraint": self.region}}
            )
            self.client.create_bucket(Bucket=self.bucket, **extra)

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
