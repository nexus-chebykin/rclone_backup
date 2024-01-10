import subprocess
import shlex
import time
from datetime import datetime
import json
import grpc
import telegram_com_pb2
import telegram_com_pb2_grpc

# get current date and time in format YYYY-MM-DD-HH-MM-SS
now = datetime.now()
date = now.strftime("%Y-%m-%d-%H-%M-%S")
source_dirs = [r'/srv/dev-disk-by-uuid-34bc3142-1570-8d4c-bf28-38ac4ab822f8/Mitabrev/Backup/1_view',
               r'/srv/dev-disk-by-uuid-34bc3142-1570-8d4c-bf28-38ac4ab822f8/Mitabrev/Backup/2_view']
target_containers = ['ya_crypt_1:', 'ya_crypt_2:']
target_dirs = [f'{target_container}backup' for target_container in target_containers]
backup_dirs = [f'{target_container}removed' for target_container in target_containers]


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.2f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.2f}Yi{suffix}"


class BasicLogger:
    def log_info(self, message):
        print('[INFO] ' + message)

    def log_error(self, message):
        print('[ERROR] ' + message)

    def log_progress(self, message):
        print('[PROGRESS] ' + message)

    def close(self):
        pass


class TelegramLogger:
    # Assumes a gRPC server satisfying the interface in telegram_com.proto
    TELEGRAM_ADDRESS = '192.168.1.107:50051'

    def __init__(self):
        self.channel = grpc.insecure_channel(self.TELEGRAM_ADDRESS)
        self.stub = telegram_com_pb2_grpc.TelegramRepeaterStub(self.channel)
        self.main_log = [None, ""]
        self.progress = [None, ""]

    def reset(self):
        self.main_log = [None, ""]
        self.progress = [None, ""]

    def ensure_done(self, job):
        # assuming unsuccessful result is -1
        times = 8
        for i in range(times):
            result = job()
            if result != -1:
                return result
            time.sleep(1 / 8 * (2 ** i))
        return -1

    def log(self, message, text, retain_previous=True):
        text += '\n'
        ID = message[0]
        prev_text = message[1]
        if ID is None:
            result = self.ensure_done(
                lambda: self.stub.SendMessage(telegram_com_pb2.MessageRequest(message=text)).message_id)
            if result == -1:
                printer.log_error('Failed to send message to telegram: ' + text)
                return
            message[0] = result
            message[1] = text
            return
        if retain_previous:
            to_send = prev_text + text
        else:
            to_send = text
        result = self.ensure_done(lambda: self.stub.SendMessage(
            telegram_com_pb2.MessageRequest(edit_id=ID, message=to_send)).message_id)
        if result == -1:
            printer.log_error('Failed to edit message in telegram: ' + text)
            return
        message[1] += text
        if result != ID:
            printer.log_error('ID of edited message changed!?')
            ID = result

    def close(self):
        self.channel.close()

    def log_info(self, message):
        self.log(self.main_log, '[INFO] ' + message)

    def log_error(self, message):
        self.log(self.main_log, '[ERROR] ' + message)

    def log_progress(self, message):
        self.log(self.progress, message, retain_previous=False)


def log_info(message):
    for logger in loggers:
        logger.log_info(message)


def log_error(message):
    for logger in loggers:
        logger.log_error(message)


def log_progress(log_line):
    json_log = json.loads(log_line)
    if 'bandwidth limi' in json_log['msg'].lower():
        log_info(json_log['msg'])
        return
    for logger in loggers:
        if 'stats' not in json_log:
            continue
        logger.log_progress(json_log['msg'])


def delete_at_least_bytes(bytes_to_delete, backup_dir):
    # first, list all files in backup_dir
    backup_dir_files = subprocess.check_output(['rclone', 'lsjson', backup_dir, '--files-only'], text=True)
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
        raise Exception('Not enough space even after deleting all files in backup_dir!')
    #     do delete
    path_to_delete = list(map(lambda x: x['Path'], backup_dir_files[:num_delete]))
    files_to_delete_as_str = '\n'.join(path_to_delete)
    log_info(
        f'Going to delete {num_delete} files from backup directory to free up {sizeof_fmt(freed)}. The files are:\n{files_to_delete_as_str}')
    t = subprocess.run(['rclone', 'delete', backup_dir, '--files-from', '-'],
                       input='\n'.join(path_to_delete), text=True)
    if t.returncode != 0:
        raise Exception('Failed to delete files from backup_dir!')
    log_info('Successfully deleted files from backup_dir')


def before_start(sync_up, target_container):
    # get available quota
    quota = subprocess.check_output(['rclone', 'about', target_container, '--json'], text=True)
    quota = json.loads(quota)
    quota = quota['free']
    log_info(f'Available quota: {sizeof_fmt(quota)}')
    dry_run_output = subprocess.check_output(sync_up + ['--dry-run'], text=True, stderr=subprocess.STDOUT)
    dry_run_output = dry_run_output.split('\n')
    last_line = json.loads(dry_run_output[-2])
    size_to_upload = last_line['stats']['bytes']
    total_files = last_line['stats']['totalTransfers']
    if size_to_upload == 0:
        log_info('Nothing to upload')
        exit(0)
    log_info(f'Files to upload: {total_files} with size: {sizeof_fmt(size_to_upload)}')
    size_to_upload = (size_to_upload + (1 << 22)) * 1.01  # add 4 MiB and 1% to be safe
    #     if we have enough quota, upload

    if size_to_upload <= quota:
        return
    #     else, delete oldest files from backup_dir
    delete_bytes_threshold = size_to_upload - quota
    delete_at_least_bytes(delete_bytes_threshold, backup_dir)

    # clean trash to actually free up space
    subprocess.check_call(['rclone', 'cleanup', target_container])


dry_run = False
for target_container, source_dir, target_dir, backup_dir in zip(target_containers, source_dirs, target_dirs,
                                                                backup_dirs):
    sync_up = \
        f'rclone sync {source_dir} {target_dir} --copy-links \
--backup-dir {backup_dir} --suffix=".version_from_{date}" \
-v --use-json-log \
--timeout 100m --retries 1'

    print(f"The command is: {sync_up}")
    sync_up = shlex.split(sync_up)
    sync_up.extend(['--bwlimit', '04:00,off 08:00,5M'])
    if dry_run:
        sync_up.append('--dry-run')

    printer = BasicLogger()
    loggers = [printer, TelegramLogger()]

    # exit(0)
    try:
        log_info(f'Checking in. Target: {target_container}')
        before_start(sync_up, target_container)
        log_info(f'Starting sync. Target: {target_container}')
        process = subprocess.Popen(sync_up, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ''):
            log_progress(line)
        process.wait()
        if process.returncode != 0:
            raise Exception(f'Process returned non-zero exit code: {process.returncode}')
        log_info('Sync finished successfully')
    except Exception as e:
        log_error(f'Exception occurred: {e}')
        raise
    for logger in loggers:
        logger.close()
