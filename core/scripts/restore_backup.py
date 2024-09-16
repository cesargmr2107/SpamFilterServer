#!/var/www/lisb/venv/bin/python
import json
import os
import sys
import boto3
import tarfile
from schema import Schema, Optional, And

from common_functions import decrypt_file

command_schema = Schema({
    "--to-restore": And(str, lambda backup_file: len(backup_file) > 0),
    Optional("--s3"): And(str, lambda bucket_str: len(bucket_str.split("/", maxsplit=1)) == 2),
    Optional("--decryption-key"): str
})


def restore_backup(options):
    backups_path = "/var/www/lisb/backups/"
    to_restore = options['--to-restore']
    to_restore_path = backups_path + to_restore

    # Download file from S3 bucket
    if '--s3' in options:
        s3_params = options['--s3']
        print(f"Dowloading '{to_restore}' from 's3://{s3_params}'")
        s3_client = boto3.client('s3')
        s3_params = s3_params.split("/", maxsplit=1)
        s3_bucket_name = s3_params[0]
        s3_file_path = os.path.join(s3_params[1], to_restore)
        s3_client.download_file(s3_bucket_name, s3_file_path, to_restore_path)

        # Add info to backups log file
        backups_log_path = '/var/www/lisb/backups/backups_log.json'
        if os.path.exists(backups_log_path):
            with open(backups_log_path, 'r') as file:
                backups_log = json.load(file)
        else:
            backups_log = {}
        if to_restore not in backups_log:
            backups_log[to_restore] = {
                'backed-up': 'Unknown',
                'timestamp': 'Unknown',
                'uploaded-to-s3': True
            }
            with open(backups_log_path, 'w') as file:
                json.dump(backups_log, file, indent=4)

    if not os.path.exists(to_restore_path):
        print(f"The specified backup file {to_restore} doesn't exist at {backups_path}")
    else:
        if to_restore.rsplit(".", 1)[1] == "enc":
            if '--decryption-key' in options:
                print("Decrypting backup file...")
                # Decrypt backup file
                decrypted_path = to_restore_path[:-4]
                decrypt_file(to_restore_path, decrypted_path, options['--decryption-key'])
                # Extract all files from backup
                print("The backup file has been restored")
                with tarfile.open(decrypted_path) as tar:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(tar, "/")
                # Remove unencrypted file
                os.remove(decrypted_path)
            else:
                print("The file is encrypted and no private key was specified")
        else:
            # Extract all files from backup
            print("The backup file has been restored")
            with tarfile.open(to_restore_path) as tar:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(tar, "/")


if __name__ == '__main__':

    try:
        # Parse command options
        options = {}
        n_args = len(sys.argv)
        for i in range(1, n_args):
            arg = sys.argv[i].split("=", maxsplit=1)
            options[arg[0]] = None if len(arg) == 1 else arg[1]

        # Validate
        validated = command_schema.validate(options)

        # Do backup if everything is correct
        restore_backup(validated)

    except Exception as e:
        print(f"An error occurred: {e.__class__.__name__} - {e}\n")
        print("Usage: restore_backup.py --to-restore=BACKUP_FILE [ --option1=val1,val2 ... ]")
        print("If options are not passed as parameters they are read from the 'conf/backups.json' file.\n")
        print("Options:\n")
        print("\t--to-restore\tThe backup file to be restored.\n")
        print("\t--s3=BUCKET_NAME/PATH\tThe S3 bucket and path where to find the backup file. "
              "If not specified, the backup file will be looked up locally at '/var/www/lisb/backups/'. "
              "Remember that, for this options to work correctly, S3 Full access needs to be enabled.\n")
        print("\t--decryption-key\tDecrypt the backup file with the specified key.")
        print("\t--help\tThis option shows all of the command options.")
