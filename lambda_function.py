import boto3
import json
import os
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

session = boto3.Session()

ec2_resource = session.resource('ec2')
s3_resource = session.resource('s3')

def get_unattached_volumes():
    unattached_volumes = []
    for volume in ec2_resource.volumes.all():
        if volume.state == 'available':  # This means the volume is not attached
            unattached_volumes.append(volume)
    return unattached_volumes

def get_unencrypted_volumes_and_snapshots():
    unencrypted_volumes = []
    unencrypted_snapshots = []
    for volume in ec2_resource.volumes.all():
        if not volume.encrypted:
            unencrypted_volumes.append(volume)
    for snapshot in ec2_resource.snapshots.filter(OwnerIds=['self']):
        if not snapshot.encrypted:
            unencrypted_snapshots.append(snapshot)
    return unencrypted_volumes, unencrypted_snapshots

def lambda_handler(event, context):
    try:
        logger.info("Getting unattached volumes...")
        unattached_volumes = get_unattached_volumes()
        logger.info("Getting unencrypted volumes and snapshots...")
        unencrypted_volumes, unencrypted_snapshots = get_unencrypted_volumes_and_snapshots()

        unattached_volumes_count = len(unattached_volumes)
        unencrypted_volumes_count = len(unencrypted_volumes)
        unencrypted_snapshots_count = len(unencrypted_snapshots)

        unattached_volumes_size = sum([volume.size for volume in unattached_volumes])
        unencrypted_volumes_size = sum([volume.size for volume in unencrypted_volumes])
        unencrypted_snapshots_size = sum([snapshot.volume_size for snapshot in unencrypted_snapshots])

        metrics = {
            "unattached_volumes_count": unattached_volumes_count,
            "unattached_volumes_size": unattached_volumes_size,
            "unencrypted_volumes_count": unencrypted_volumes_count,
            "unencrypted_volumes_size": unencrypted_volumes_size,
            "unencrypted_snapshots_count": unencrypted_snapshots_count,
            "unencrypted_snapshots_size": unencrypted_snapshots_size,
        }

        metrics_json = json.dumps(metrics)

        # Write the metrics to a file
        logger.info("Writing metrics to a file...")
        with open('/tmp/metrics.json', 'w') as file:
            file.write(metrics_json)

        # Upload the file to an S3 bucket
        bucket_name = os.environ['BUCKET_NAME']  # Get the bucket name from environment variables
        logger.info(f"Uploading file to S3 bucket {bucket_name}...")
        s3_resource.Bucket(bucket_name).upload_file(Filename='/tmp/metrics.json', Key='metrics.json')
        logger.info("File uploaded successfully.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
