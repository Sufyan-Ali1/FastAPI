"""
Lesson 58 - gRPC alongside FastAPI
----------------------------------
A self-contained, RUNNABLE gRPC demo:

    1. compiles user.proto -> generated Python code (if not already present)
    2. starts a gRPC SERVER implementing UserService
    3. a CLIENT calls it: a UNARY method (GetUser) and a SERVER-STREAMING
       method (ListUsers), printing the typed replies

In a real system, FastAPI would be the public REST edge and services like this
would talk gRPC internally (see theory.md).

    pip install grpcio grpcio-tools

How to run (from inside this folder):

    python main.py
"""

import os
import subprocess
import sys
from concurrent import futures

import grpc

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# 1. Compile user.proto -> user_pb2.py + user_pb2_grpc.py (once).
# ---------------------------------------------------------------------------
def ensure_generated_code() -> None:
    pb2 = os.path.join(HERE, "user_pb2.py")
    if not os.path.exists(pb2):
        subprocess.run(
            [sys.executable, "-m", "grpc_tools.protoc", "-I", HERE,
             f"--python_out={HERE}", f"--grpc_python_out={HERE}",
             os.path.join(HERE, "user.proto")],
            check=True,
        )


ensure_generated_code()

# Import the generated code (available after compilation above).
import user_pb2  # noqa: E402
import user_pb2_grpc  # noqa: E402

# Fake "database" the service serves.
_USERS = {
    1: ("Ada", "ada@example.com"),
    2: ("Alan", "alan@example.com"),
    3: ("Grace", "grace@example.com"),
}


# ---------------------------------------------------------------------------
# 2. SERVER: implement the service methods (a "servicer").
# ---------------------------------------------------------------------------
class UserServicer(user_pb2_grpc.UserServiceServicer):
    def GetUser(self, request, context):
        # UNARY: request.user_id is a typed int32; return a typed UserReply.
        row = _USERS.get(request.user_id)
        if row is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
        name, email = row
        return user_pb2.UserReply(id=request.user_id, name=name, email=email)

    def ListUsers(self, request, context):
        # SERVER STREAMING: yield a stream of replies, one per user.
        for uid, (name, email) in _USERS.items():
            yield user_pb2.UserReply(id=uid, name=name, email=email)


def serve() -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
    port = server.add_insecure_port("127.0.0.1:0")  # 0 = pick a free port
    server.start()
    return server, port


# ---------------------------------------------------------------------------
# 3. CLIENT: call the server through a generated stub.
# ---------------------------------------------------------------------------
def main() -> None:
    server, port = serve()
    print(f"gRPC server listening on 127.0.0.1:{port}\n")

    with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
        stub = user_pb2_grpc.UserServiceStub(channel)

        # UNARY call - feels like a local function call, but it's over the wire.
        reply = stub.GetUser(user_pb2.GetUserRequest(user_id=1))
        print(f"[unary]  GetUser(1) -> id={reply.id} name={reply.name} email={reply.email}")

        # SERVER-STREAMING call - iterate the streamed replies.
        print("[stream] ListUsers() ->")
        for u in stub.ListUsers(user_pb2.ListUsersRequest()):
            print(f"           id={u.id} name={u.name}")

        # A NOT_FOUND error propagates as a gRPC status.
        try:
            stub.GetUser(user_pb2.GetUserRequest(user_id=999))
        except grpc.RpcError as e:
            print(f"[error]  GetUser(999) -> {e.code().name}: {e.details()}")

    server.stop(grace=None)


if __name__ == "__main__":
    main()
