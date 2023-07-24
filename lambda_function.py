import os
import json
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_ec2_metrics():
    """
    Retrieves the metrics from the EC2 volumes and snapshots.

    :return: A list of metrics.
    """
    metrics = []
    ec2 = boto3.resource('ec2')

    try:
        for volume in ec2.volumes.all():
            if not volume.attachments and not volume.encrypted:
                metrics.append({
                    'VolumeId': volume.id,
                    'Size': volume.size
                })
                
        for snapshot in ec2.snapshots.filter(OwnerIds=['self']):
            if not snapshot.encrypted:
                metrics.append({
                    'SnapshotId': snapshot.id,
                    'Size': snapshot.volume_size
                })
    except Exception as e:
        logger.error(f"Error while getting EC2 metrics: {str(e)}")
        raise e

    if not metrics:
        logger.info("No unattached and unencrypted volumes or snapshots found.")

    return metrics

def save_metrics_to_s3(metrics):
    """
    Saves the given metrics to an S3 bucket.

    :param metrics: The metrics to save.
    """
    bucket_name = os.getenv('BUCKET_NAME')
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"ec2_metrics_{timestamp}.json"

    s3 = boto3.resource('s3')

    try:
        s3.Object(bucket_name, file_name).put(
            Body=json.dumps(metrics, indent=4)
        )
        logger.info(f"Metrics saved to S3 bucket {bucket_name} as {file_name}")
    except s3.meta.client.exceptions.NoSuchBucket as e:
        logger.error(f"Bucket {bucket_name} does not exist: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error while saving metrics to S3: {str(e)}")
        raise e

def lambda_handler(event, context):
    """
    AWS Lambda function entry point.

    :param event: The Lambda event data.
    :param context: The Lambda context data.
    """
    if 'BUCKET_NAME' not in os.environ:
        logger.error("BUCKET_NAME environment variable not set.")
        raise ValueError("BUCKET_NAME environment variable not set.")

    try:
        metrics = get_ec2_metrics()
        save_metrics_to_s3(metrics)
    except Exception as e:
        logger.error(f"Error in Lambda function: {str(e)}")
        raise e
