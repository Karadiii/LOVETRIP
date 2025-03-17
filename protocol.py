class Protocol:
    @staticmethod
    def send(socket, message: str):
        socket.sendall(f"{message}#".encode('utf-8'))

    @staticmethod
    def receive(socket):
        data = b''
        while True:
            chunk = socket.recv(1024)  # Reduced buffer size slightly
            if not chunk:  # Connection closed
                return None
            data += chunk
            if b'#' in chunk:  # Check if delimiter is in this chunk
                break
        return data.decode('utf-8').rstrip('#')