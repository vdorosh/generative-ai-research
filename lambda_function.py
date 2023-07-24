import boto3
import json
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_ec2_resource():
    try:
        # If AWS_PROFILE environment variable is set, use it
        profile = os.environ['AWS_PROFILE']
        session = boto3.Session(profile_name='softserve')
    except KeyError:
        # If not, default to the instance's IAM role
        session = boto3.Session()
    return session.resource('ec2')

ec2_resource = get_ec2_resource()
s3_resource = boto3.resource('s3')

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

def main():
    try:
        # Check if BUCKET_NAME environment variable is set
        if 'BUCKET_NAME' not in os.environ:
            raise Exception('BUCKET_NAME environment variable is not set')

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

        metrics_json = json.dumps(metrics, indent=4)

        # Write the metrics to a file
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        filename = f'/tmp/metrics-{timestamp}.json'
        logger.info("Writing metrics to a file...")
        with open(filename, 'w') as file:
            file.write(metrics_json)

        # Upload the file to an S3 bucket
        bucket_name = os.environ['BUCKET_NAME']  # Get the bucket name from environment variables
        logger.info(f"Uploading file to S3 bucket {bucket_name}...")
        s3_resource.Bucket(bucket_name).upload_file(Filename=filename, Key=f'metrics-{timestamp}.json')
        logger.info("File uploaded successfully.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

def lambda_handler(event, context):
    main()

if __name__ == "__main__":
    main()
