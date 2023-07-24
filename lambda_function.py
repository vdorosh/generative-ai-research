import os
import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from time import sleep

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
        raise Exception("Environment variable not set: " + str(e))

    print("Collecting metrics from EC2 volumes and snapshots...")

    metrics = {
        "UnattachedVolumes": get_metrics(get_unattached_volumes()),
        "UnencryptedVolumes": get_metrics(get_unencrypted_volumes()),
        "UnencryptedSnapshots": get_metrics(get_unencrypted_snapshots())
    }

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    file_name = f"{bucket_path}/metrics-{timestamp}.json"

    print(f"Writing metrics to S3 bucket {bucket_name} at {file_name}...")

    s3.put_object(
        Body=json.dumps(metrics, indent=4),
        Bucket=bucket_name,
        Key=file_name
    )

    print("Metrics written successfully to S3.")

    return {
        'statusCode': 200,
        'body': json.dumps(metrics)
    }


def get_unattached_volumes():
    """Return a list of unattached volumes."""
    try:
        response = retry_on_failure(ec2.describe_volumes)
        return collect_metrics_from_volumes(response['Volumes'], 'available')
    except ClientError as e:
        print(f"Failed to get unattached volumes: {e}")
        return []


def get_unencrypted_volumes():
    """Return a list of unencrypted volumes."""
    try:
        response = retry_on_failure(ec2.describe_volumes)
        return collect_metrics_from_volumes(response['Volumes'], 'unencrypted')
    except ClientError as e:
        print(f"Failed to get unencrypted volumes: {e}")
        return []


def get_unencrypted_snapshots():
    """Return a list of unencrypted snapshots."""
    try:
        response = retry_on_failure(ec2.describe_snapshots, OwnerIds=['self'])
        return collect_metrics_from_snapshots(response['Snapshots'])
    except ClientError as e:
        print(f"Failed to get unencrypted snapshots: {e}")
        return []


def retry_on_failure(func, **kwargs):
    """Retry the function in case of AWS RequestLimitExceeded error."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            return func(**kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'RequestLimitExceeded' and retries < MAX_RETRIES:
                sleep(BACKOFF_FACTOR ** retries)
                retries += 1
            else:
                raise


def collect_metrics_from_volumes(volumes, filter_type):
    """Collect metrics from volumes based on the filter type."""
    metrics = []
    for volume in volumes:
        if (filter_type == 'available' and volume['State'] == 'available') or \
           (filter_type == 'unencrypted' and not volume.get('KmsKeyId')):
            metrics.append({"VolumeId": volume['VolumeId'], "Size": volume['Size']})
    print(f"Collected {len(metrics)} {filter_type} volumes.")
    return metrics


def collect_metrics_from_snapshots(snapshots):
    """Collect metrics from snapshots."""
    metrics = []
    for snapshot in snapshots:
        if not snapshot.get('KmsKeyId'):
            metrics.append({"SnapshotId": snapshot['SnapshotId'], "Size": snapshot['VolumeSize']})
    print(f"Collected {len(metrics)} unencrypted snapshots.")
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
    print(lambda_handler({}, {}))


if __name__ == "__main__":
    main()
