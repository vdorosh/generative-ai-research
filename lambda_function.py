import boto3
import json

session = boto3.Session(profile_name='softserve-sso')

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

try:
    unattached_volumes = get_unattached_volumes()
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
    with open('metrics.json', 'w') as file:
        file.write(metrics_json)

    # Upload the file to an S3 bucket
    bucket_name = 'your-bucket-name'  # Replace with your bucket name
    s3_resource.Bucket(bucket_name).upload_file(Filename='metrics.json', Key='metrics.json')

except Exception as e:
    print(f"An error occurred: {e}")
