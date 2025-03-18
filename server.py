import socket
from threading import Thread
from protocol import Protocol
import os

QUEUE_SIZE = 10
IP = '0.0.0.0'
PORT = 8080
MOVIE_DIR = r"E:\Movies"  # Use your Movies folder


def handle_connection(client_socket, client_address):
    try:
        # Send movie list
        movie_files = [f for f in os.listdir(MOVIE_DIR) if f.lower().endswith(('.mp4', '.mkv', '.avi'))]
        movie_list = ";".join(movie_files)
        Protocol.send(client_socket, f"MOVIES:{movie_list}")

        while True:
            message = Protocol.receive(client_socket)
            if not message:
                break
            if message.startswith("SELECT:"):
                movie_name = message.split(":", 1)[1]
                movie_path = os.path.join(MOVIE_DIR, movie_name)
                if os.path.exists(movie_path):
                    Protocol.send(client_socket, f"STREAMING:{movie_name}")
                    stream_movie(client_socket, movie_path)
                else:
                    Protocol.send(client_socket, "ERROR:Movie not found")
            else:
                response = f"Message received. Length: {len(message)}"
                Protocol.send(client_socket, response)
    except socket.error as err:
        print('Socket error:', err)
    finally:
        client_socket.close()


def stream_movie(client_socket, movie_path):
    """Stream the movie file in 1MB chunks, stop if client requests."""
    client_socket.setblocking(False)  # Non-blocking to check for messages
    with open(movie_path, 'rb') as f:
        while True:
            chunk = f.read(1048576)  # 1MB chunks
            if not chunk:
                break
            try:
                client_socket.sendall(chunk)
                # Check for incoming message without blocking
                try:
                    message = Protocol.receive(client_socket)
                    if message == "STOP_STREAM":
                        print(f"Client requested stop for {movie_path}")
                        break
                except BlockingIOError:
                    pass  # No message waiting, continue streaming
            except socket.error as e:
                print(f"Stream error: {e}")
                break
    client_socket.setblocking(True)  # Restore blocking mode
    Protocol.send(client_socket, "STREAM_END")


def main():
    if not os.path.exists(MOVIE_DIR):
        os.makedirs(MOVIE_DIR)
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
