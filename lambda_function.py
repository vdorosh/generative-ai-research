import os
import json
import boto3
import logging
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
from datetime import datetime
from time import sleep

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retry settings
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

# AWS services clients
session = boto3.Session(region_name=os.getenv('AWS_REGION'))
ec2 = session.client('ec2')
s3 = session.client('s3')

def lambda_handler(event, context):
    """Main Lambda function handler."""
    try:
        bucket_name = os.environ['BUCKET_NAME']
        bucket_path = os.getenv('BUCKET_PATH', '')
    except KeyError as e:
        logger.error("Missing environment variable: %s", str(e))
        raise Exception("Environment variable not set: " + str(e))

    logger.info("Collecting metrics from EC2 volumes and snapshots...")

    metrics = {
        "UnattachedVolumes": get_metrics(get_unattached_volumes()),
        "UnencryptedVolumes": get_metrics(get_unencrypted_volumes()),
        "UnencryptedSnapshots": get_metrics(get_unencrypted_snapshots())
    }

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    file_name = f"{bucket_path}/metrics-{timestamp}.json"

    logger.info("Writing metrics to S3 bucket %s at %s...", bucket_name, file_name)

    try:
        s3.put_object(
            Body=json.dumps(metrics, indent=4),
            Bucket=bucket_name,
            Key=file_name
        )
    except ClientError as e:
        logger.error("Failed to write metrics to S3: %s", e)
        raise e

    logger.info("Metrics written successfully to S3.")

    return {
        'statusCode': 200,
        'body': json.dumps(metrics)
    }

def get_unattached_volumes():
    """Return a list of unattached volumes."""
    try:
        return collect_metrics_from_volumes('available')
    except ClientError as e:
        logger.error("Failed to get unattached volumes: %s", e)
        return []
    except (BotoCoreError, NoCredentialsError) as e:
        logger.error("AWS error: %s", e)
        raise e

def get_unencrypted_volumes():
    """Return a list of unencrypted volumes."""
    try:
        return collect_metrics_from_volumes('unencrypted')
    except ClientError as e:
        logger.error("Failed to get unencrypted volumes: %s", e)
        return []
    except (BotoCoreError, NoCredentialsError) as e:
        logger.error("AWS error: %s", e)
        raise e

def get_unencrypted_snapshots():
    """Return a list of unencrypted snapshots."""
    try:
        return collect_metrics_from_snapshots()
    except ClientError as e:
        logger.error("Failed to get unencrypted snapshots: %s", e)
        return []
    except (BotoCoreError, NoCredentialsError) as e:
        logger.error("AWS error: %s", e)
        raise e

def collect_metrics_from_volumes(filter_type):
    """Collect metrics from volumes based on the filter type."""
    paginator = ec2.get_paginator('describe_volumes')
    metrics = []

    for page in paginator.paginate():
        for volume in page['Volumes']:
            if (filter_type == 'available' and volume['State'] == 'available') or \
            (filter_type == 'unencrypted' and not volume.get('KmsKeyId')):
                metrics.append({"VolumeId": volume['VolumeId'], "Size": volume['Size']})

    logger.info("Collected %d %s volumes.", len(metrics), filter_type)
    return metrics

def collect_metrics_from_snapshots():
    """Collect metrics from snapshots."""
    paginator = ec2.get_paginator('describe_snapshots')
    metrics = []

    for page in paginator.paginate(OwnerIds=['self']):
        for snapshot in page['Snapshots']:
            if not snapshot.get('KmsKeyId'):
                metrics.append({"SnapshotId": snapshot['SnapshotId'], "Size": snapshot['VolumeSize']})

    logger.info("Collected %d unencrypted snapshots.", len(metrics))
    return metrics

def get_metrics(data):
    """Get the metrics for the provided data."""
    return {
        "Count": len(data),
        "TotalSize": sum([item['Size'] for item in data]),
        "Details": data
    }

def main():
    """Test the lambda function locally."""
    logger.info(lambda_handler({}, {}))

if __name__ == "__main__":
    main()
