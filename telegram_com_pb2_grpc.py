# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import telegram_com_pb2 as telegram__com__pb2


class TelegramRepeaterStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.SendMessage = channel.unary_unary(
                '/telegram_com.TelegramRepeater/SendMessage',
                request_serializer=telegram__com__pb2.MessageRequest.SerializeToString,
                response_deserializer=telegram__com__pb2.MessageID.FromString,
                )


class TelegramRepeaterServicer(object):
    """Missing associated documentation comment in .proto file."""

    def SendMessage(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_TelegramRepeaterServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'SendMessage': grpc.unary_unary_rpc_method_handler(
                    servicer.SendMessage,
                    request_deserializer=telegram__com__pb2.MessageRequest.FromString,
                    response_serializer=telegram__com__pb2.MessageID.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'telegram_com.TelegramRepeater', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class TelegramRepeater(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def SendMessage(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/telegram_com.TelegramRepeater/SendMessage',
            telegram__com__pb2.MessageRequest.SerializeToString,
            telegram__com__pb2.MessageID.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)