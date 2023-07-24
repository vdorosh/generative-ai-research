import os
import json
import boto3
import logging
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS services client
session = boto3.Session()
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

    metrics = {}

    # Iterate over each region
    regions = session.get_available_regions('ec2')
    for region in regions:
        try:
            ec2 = session.client('ec2', region_name=region)
            region_metrics = {
                "UnattachedVolumes": get_metrics(get_unattached_volumes(ec2)),
                "UnencryptedVolumes": get_metrics(get_unencrypted_volumes(ec2)),
                "UnencryptedSnapshots": get_metrics(get_unencrypted_snapshots(ec2))
            }
            metrics[region] = region_metrics
        except ClientError as e:
            if "AuthFailure" in str(e):
                # Skip regions with authentication failure and suppress the error message
                logger.warning("Region %s is not enabled for your account. Skipping...", region)
                continue
            else:
                logger.error("Failed to process region %s: %s", region, e)

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

def get_unattached_volumes(ec2):
    """Return a list of unattached volumes."""
    try:
        return collect_metrics_from_volumes(ec2, 'available')
    except ClientError as e:
        logger.error("Failed to get unattached volumes: %s", e)
        return []
    except (BotoCoreError, NoCredentialsError) as e:
        logger.error("AWS error: %s", e)
        raise e

def get_unencrypted_volumes(ec2):
    """Return a list of unencrypted volumes."""
    try:
        return collect_metrics_from_volumes(ec2, 'unencrypted')
    except ClientError as e:
        logger.error("Failed to get unencrypted volumes: %s", e)
        return []
    except (BotoCoreError, NoCredentialsError) as e:
        logger.error("AWS error: %s", e)
        raise e

def get_unencrypted_snapshots(ec2):
    """Return a list of unencrypted snapshots."""
    try:
        return collect_metrics_from_snapshots(ec2)
    except ClientError as e:
        logger.error("Failed to get unencrypted snapshots: %s", e)
        return []
    except (BotoCoreError, NoCredentialsError) as e:
        logger.error("AWS error: %s", e)
        raise e

def collect_metrics_from_volumes(ec2, filter_type):
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

def collect_metrics_from_snapshots(ec2):
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
