import json
import time

try:
    import grpc
    import telegram_com_pb2
    import telegram_com_pb2_grpc
except ImportError:
    print('[Warning] gRPC not found! Disabling telegram logging')
    grpc = None


class BasicLogger:
    def log_info(self, message):
        print('[INFO] ' + message)

    def log_error(self, message):
        print('[ERROR] ' + message)

    def log_progress(self, message):
        print('[PROGRESS] ' + message)

    def reset(self):
        pass


class TelegramLogger:
    # Assumes a gRPC server satisfying the interface in telegram_com.proto
    TELEGRAM_ADDRESS = '192.168.1.107:50051'

    def __init__(self, printer: BasicLogger):
        self.channel = grpc.insecure_channel(self.TELEGRAM_ADDRESS)
        self.stub = telegram_com_pb2_grpc.TelegramRepeaterStub(self.channel)
        self.main_log = [None, ""]
        self.progress = [None, ""]
        self.printer = printer

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

    @staticmethod
    def ensure_fits(text):
        # TG messages are 4096 symbols long
        snip = '\n<--snip-->'
        maxlen = (
                4096 - len(snip)
                - 10  # to be certain
        )
        if len(text) > maxlen:
            text = text[:maxlen] + snip
        return text

    def log(self, message, text, retain_previous=True):
        try:
            self._log(message, text, retain_previous)
        except Exception as e:
            self.printer.log_error(e.add_note("Failed to log to telegram with this exception"))

    def _log(self, message, text, retain_previous):
        text += '\n'
        ID = message[0]
        prev_text = message[1]
        if ID is None:
            result = self.ensure_done(
                lambda: self.stub.SendMessage(
                    telegram_com_pb2.MessageRequest(message=self.ensure_fits(text))
                ).message_id
            )
            if result == -1:
                self.printer.log_error('Failed to send message to telegram: ' + text)
                return
            message[0] = result
            message[1] = text
            return
        if retain_previous:
            to_send = prev_text + text
        else:
            to_send = text
        result = self.ensure_done(lambda: self.stub.SendMessage(
            telegram_com_pb2.MessageRequest(edit_id=ID, message=self.ensure_fits(to_send))).message_id)
        if result == -1:
            self.printer.log_error('Failed to edit message in telegram: ' + text)
            return
        message[1] += text
        if result != ID:
            self.printer.log_error('ID of edited message changed!?')
            ID = result

    def log_info(self, message):
        self.log(self.main_log, '[INFO] ' + message)

    def log_error(self, message):
        self.log(self.main_log, '[ERROR] ' + message)

    def log_progress(self, message):
        self.log(self.progress, message, retain_previous=False)


printer = BasicLogger()
loggers = [printer] \
          + ([TelegramLogger(printer)] if grpc else [])


def log_info(message):
    for logger in loggers:
        logger.log_info(message)


def log_error(message):
    for logger in loggers:
        logger.log_error(message)


def log_progress(log_line):
    print(log_line)
    try:
        json_log = json.loads(log_line)
    except json.decoder.JSONDecodeError as e:
        log_error(f'Could not decode json: {log_line}')
        return

    if 'bandwidth' in json_log['msg'].lower():
        log_info(json_log['msg'])
        return

    for logger in loggers:
        if isinstance(logger, BasicLogger):
            logger.log_progress(json_log['msg'])
            continue
        if 'stats' not in json_log:
            continue
        logger.log_progress(json_log['msg'])


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.2f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.2f}Yi{suffix}"
