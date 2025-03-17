import socket
from gui import ClientGUI
from PyQt6.QtWidgets import QApplication
import sys

IP = '127.0.0.1'
PORT = 8080


def main():
    print('Connecting...')
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        my_socket.connect((IP, PORT))
        app = QApplication(sys.argv)  # Initialize the Qt application
        gui = ClientGUI(my_socket)    # Create GUI with socket
        sys.exit(app.exec())          # Run the Qt event loop
    except socket.error as err:
        print('Received socket error ' + str(err))
    finally:
        my_socket.close()


if __name__ == '__main__':
    main()
