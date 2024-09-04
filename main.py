import json
import pathlib
import subprocess
import shlex
from datetime import datetime
from loggers import *

# get current date and time in format YYYY-MM-DD-HH-MM-SS
source_dirs = [
    # r'/home/simon/tmp'
    r'/srv/dev-disk-by-uuid-34bc3142-1570-8d4c-bf28-38ac4ab822f8/Mitabrev/Backup/1_view',
    r'/srv/dev-disk-by-uuid-34bc3142-1570-8d4c-bf28-38ac4ab822f8/Mitabrev/Backup/2_view'
]
target_containers = [
    # 'ya_chunk:zzz'
    'ya_chunk_papa_1:',
    'ya_chunk_simon_2:'
]
target_dirs = [f'{target_container}backup' for target_container in target_containers]
backup_dirs = [f'{target_container}removed' for target_container in target_containers]


def ensure_single_instance():
    import fcntl, sys
    lockfile = 'lock.lock'
    fp = open(lockfile, 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        # another instance is running
        sys.exit(1)


def delete_at_least_bytes(bytes_to_delete, backup_dir):
    # first, list all files in backup_dir
    backup_dir_files = subprocess.check_output(['rclone', 'lsjson', backup_dir, '--files-only', '-R'], text=True)
    backup_dir_files = json.loads(backup_dir_files)
    #     sort them by date. Important: not date of modification, but date of deletion!
    for file in backup_dir_files:
        pos = file['Name'].rfind('.version_from_')
        file['sort_by'] = 1 << 60
        if pos == -1:
            log_info(f'File {file["Name"]} does not have a date in its name. Strange')
            continue
        pos += len('.version_from_')
        file['sort_by'] = datetime.strptime(file['Name'][pos:], '%Y-%m-%d-%H-%M-%S').timestamp()
    backup_dir_files.sort(key=lambda x: x['sort_by'])
    # find out how much do we need to delete
    freed = 0
    num_delete = 0
    for file in backup_dir_files:
        freed += file['Size']
        num_delete += 1
        if freed >= bytes_to_delete:
            break
    else:
        raise Exception(
            f'Not enough space even after deleting all files in backup_dir: {backup_dir}: {bytes_to_delete} > {freed}')
    #     do delete
    path_to_delete = list(map(lambda x: x['Path'], backup_dir_files[:num_delete]))
    files_to_delete_as_str = '\n'.join(path_to_delete)
    log_info(
        f'Going to delete {num_delete} files from backup directory to free up {sizeof_fmt(freed)}. The files are:\n{files_to_delete_as_str}')
    if dry_run:
        return
    t = subprocess.run(['rclone', 'delete', backup_dir, '--files-from', '-'],
                       input='\n'.join(path_to_delete), text=True)
    if t.returncode != 0:
        raise Exception('Failed to delete files from backup_dir!')
    log_info('Successfully deleted files from backup_dir')


def before_start(sync_up, source_dir, target_container) -> bool:
    # Returns whether to proceed with backup

    # check that macrium is not running backup under that directory
    hasBackupRunning = next(pathlib.Path(source_dir).glob('**/backup_running'), None)
    if hasBackupRunning:
        log_info('Macrium is currently running a backup, skipping')
        return False

    # get available quota
    quota = subprocess.check_output(['rclone', 'about', target_container, '--json'], text=True)
    quota = json.loads(quota)
    quota = quota['free']
    log_info(f'Available quota: {sizeof_fmt(quota)}')
    dry_run_output = subprocess.check_output(sync_up + ([] if dry_run else ['--dry-run']), text=True,
                                             stderr=subprocess.STDOUT)
    dry_run_output = dry_run_output.split('\n')

    files_to_upload = []
    for line in dry_run_output:
        try:
            parsed = json.loads(line)
            if parsed.get('skipped') == 'copy':
                files_to_upload.append(parsed['object'])
        except Exception as e:
            pass

    last_line = json.loads(dry_run_output[-2])
    size_to_upload = last_line['stats']['bytes']
    total_files = last_line['stats']['totalTransfers']

    if size_to_upload == 0:
        log_info('Nothing to upload (?)')
        return False

    log_info(f'Files to upload: {total_files} with size: {sizeof_fmt(size_to_upload)}')
    log_info('The files are:\n' + '\n'.join(files_to_upload[:10]) + ('\n...' if len(files_to_upload) > 10 else ''))

    size_to_upload = (size_to_upload + (1 << 22)) * 1.01  # add 4 MiB and 1% to be safe
    #     if we have enough quota, upload

    if size_to_upload <= quota:
        return True
    #     else, delete oldest files from backup_dir
    delete_bytes_threshold = size_to_upload - quota
    delete_at_least_bytes(delete_bytes_threshold, backup_dir)

    # clean trash to actually free up space
    if dry_run:
        return True
    subprocess.check_call(['rclone', 'cleanup', target_container])


ensure_single_instance()

dry_run = False
for target_container, source_dir, target_dir, backup_dir in zip(target_containers, source_dirs, target_dirs,
                                                                backup_dirs):
    time_now_string = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    sync_up = \
        f'rclone sync {source_dir} {target_dir} --copy-links \
--backup-dir {backup_dir} --suffix=".version_from_{time_now_string}" \
--timeout 100m --retries 1 \
-v --use-json-log'
    # also some flags added later

    print(f"The command is: {sync_up}")
    sync_up = shlex.split(sync_up)

    # exit(0)

    for logger in loggers:
        logger.reset()

    try:
        log_info(f'Checking in. Target: {target_container}')
        proceed_uploading = before_start(sync_up,  source_dir, target_container)
        if not proceed_uploading:
            continue
        log_info(f'Starting sync. Target: {target_container}')
        # sync_up.append("--checksum") # not needed, if remote supports hashing, integrity check happens automatically
        sync_up.extend(['--bwlimit', '00:00,off 09:00,5M'])
        if dry_run:
            sync_up.append('--dry-run')
        process = subprocess.Popen(sync_up, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ''):
            log_progress(line)
        process.wait()
        if process.returncode != 0:
            raise Exception(f'Process returned non-zero exit code: {process.returncode}')
        log_info('Sync finished successfully')
    except json.decoder.JSONDecodeError as e:
        log_error(f'Could not decode json: {e.doc}')
        raise
    except Exception as e:
        log_error(f'Exception occurred: {e}')
        raise
