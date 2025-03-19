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
    """Stream the movie file in 1MB chunks."""
    total_sent = 0
    with open(movie_path, 'rb') as f:
        while True:
            chunk = f.read(1048576)  # 1MB chunks
            if not chunk:
                print(f"Finished reading {movie_path}, sent {total_sent // 1024 // 1024}MB")
                break
            try:
                client_socket.sendall(chunk)
                total_sent += len(chunk)
                print(f"Sent {total_sent // 1024 // 1024}MB")
            except socket.error as e:
                print(f"Stream error: {e}")
                break
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
