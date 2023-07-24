import boto3

# Create a session using your AWS credentials
session = boto3.Session(
    aws_access_key_id='YOUR_ACCESS_KEY',
    aws_secret_access_key='YOUR_SECRET_KEY',
    region_name='YOUR_REGION_NAME' # e.g. 'us-west-2'
)

ec2_resource = session.resource('ec2')

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

unattached_volumes = get_unattached_volumes()
unencrypted_volumes, unencrypted_snapshots = get_unencrypted_volumes_and_snapshots()

unattached_volumes_count = len(unattached_volumes)
unencrypted_volumes_count = len(unencrypted_volumes)
unencrypted_snapshots_count = len(unencrypted_snapshots)

unattached_volumes_size = sum([volume.size for volume in unattached_volumes])
unencrypted_volumes_size = sum([volume.size for volume in unencrypted_volumes])
unencrypted_snapshots_size = sum([snapshot.volume_size for snapshot in unencrypted_snapshots])

print(f"Number of unattached volumes: {unattached_volumes_count}")
print(f"Total size of unattached volumes: {unattached_volumes_size} GB")
print(f"Number of unencrypted volumes: {unencrypted_volumes_count}")
print(f"Total size of unencrypted volumes: {unencrypted_volumes_size} GB")
print(f"Number of unencrypted snapshots: {unencrypted_snapshots_count}")
print(f"Total size of unencrypted snapshots: {unencrypted_snapshots_size} GB")
