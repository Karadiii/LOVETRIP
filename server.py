import socket
from threading import Thread
from protocol import Protocol

QUEUE_SIZE = 10
IP = '0.0.0.0'
PORT = 8080


def handle_connection(client_socket, client_address):
    try:
        Protocol.send(client_socket, "Connected")
        while True:
            message = Protocol.receive(client_socket)
            if not message:
                break
            response = f"Message received. Length: {len(message)}"
            Protocol.send(client_socket, response)
    except socket.error as err:
        print('Socket error:', err)
    client_socket.close()


def main():
    """
    starts the server, starting thread for each client
    on an infinite loop.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((IP, PORT))
        server_socket.listen(QUEUE_SIZE)
        print("Listening for connections on port %d" % PORT)

        while True:
            client_socket, client_address = server_socket.accept()
            thread = Thread(target=handle_connection, args=(client_socket, client_address))
            thread.start()
    except socket.error as err:
        print('Received socket exception - ' + str(err))
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
