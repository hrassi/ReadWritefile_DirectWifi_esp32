import network
import socket
import select
from machine import Pin
import os  # Import the os module for file operations

# Set up the onboard LED pin (usually GPIO 2 on ESP32 boards)
led = Pin(2, Pin.OUT)
led.off()  # Turn off the LED initially

# Configure the ESP32 as an Access Point
ssid = 'Sam_Ap'
password = '12345678'

# Function to activate the Access Point
def activate_access_point():
    print('Activating Access Point...')
    ap = network.WLAN(network.AP_IF)  # Initialize the WLAN interface in AP mode
    ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA_WPA2_PSK)  # Set WPA2 security
    ap.active(True)  # Activate the AP mode

    while not ap.active():
        pass  # Wait until the AP mode is active

    print('Access Point Active')
    print('AP Config:', ap.ifconfig())  # Print the network configuration
    ip_address = ap.ifconfig()[0]
    return ap, ip_address

# Function to read and format content of sam.txt
def read_file_content():
    try:
        with open('sam.txt', 'r') as f:
            content = f.readlines()
            return "<br>".join(content)
    except OSError:
        return "File not found."

# Define the HTML for the web interface with enhanced UI
html_template = """<!DOCTYPE html>
<html>
<head>
    <title>Sam.txt File</title>
    <style>
        body {{background-color: gray; color: white; text-align: center; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;}}
        .container {{border: 5px double white; padding: 20px; width: 80%;}}
        h1 {{font-size: 4em; font-weight: bold; margin: 20px;}}
        form {{font-size: 2em;}}
        input[type="text"] {{font-size: 2em; padding: 10px; width: 90%;}}
        button {{font-size: 2em; padding: 10px 20px; margin-top: 20px;}}
        #fileContent {{border: 2px solid white; padding: 10px; text-align: left; font-size: 1.5em; margin-top: 20px; height: 200px; overflow-y: scroll; white-space: pre-wrap;}}
    </style>
</head>
<body>
    <div class="container">
        <h1>Sam.txt File</h1>
        <form action="/submit" method="get">
            <input type="text" name="log_text" placeholder="Enter text here" required>
            <button type="submit">Submit</button>
        </form>
        <button onclick="clearFile()">Clear All</button>
        <div id="fileContent">{file_content}</div>
    </div>
    <script>
        function clearFile() {{
            fetch('/clear');
            setTimeout(function() {{ location.reload(); }}, 500); // Reload to refresh file content
        }}
    </script>
</body>
</html>
"""

# Helper function to convert IP address string to bytes
def ip_to_bytes(ip):
    return bytes(map(int, ip.split('.')))

# Function to handle DNS queries
def handle_dns_request(data, addr, dns, ip_address):
    response = data[:2] + b'\x81\x80'  # Response flags
    response += data[4:6] + data[4:6] + b'\x00\x00\x00\x00'  # Questions and Answers count
    response += data[12:] + b'\xc0\x0c' + b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'
    response += ip_to_bytes(ip_address)
    dns.sendto(response, addr)

# Function to clear the sam.txt file by deleting it
def clear():
    try:
        # Remove the file if it exists
        if 'sam.txt' in os.listdir():  # Check if the file exists
            os.remove('sam.txt')  # Delete the file
            print("sam.txt has been deleted.")
        else:
            print("sam.txt does not exist.")

    except OSError as e:
        print("Error handling file:", e)

# Main function to set up the server and DNS
def start_server():
    server_running = True
    while server_running:
        ap, ip_address = activate_access_point()

        # Set up the web server
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(1)

        print('Listening on', addr)

        # Set up a simple DNS server
        dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        dns.bind(('0.0.0.0', 53))

        while True:
            r, _, _ = select.select([s, dns], [], [])
            for ready_socket in r:
                if ready_socket == s:
                    # Handle HTTP request
                    cl, addr = s.accept()
                    print('Client connected from', addr)
                    led.on()
                    try:
                        request = cl.recv(1024)
                        request_str = request.decode()
                        print("Request:", request_str)

                        if 'GET /submit?' in request_str:
                            log_text = request_str.split('log_text=')[1].split(' ')[0]
                            log_text = log_text.replace('+', ' ')  # Replace '+' with space
                            with open('sam.txt', 'a') as f:
                                f.write(log_text + '\n')
                        elif 'GET /clear' in request_str:
                            clear()  # Call the clear function

                        file_content = read_file_content()
                        response = 'HTTP/1.1 200 OK\nContent-Type: text/html\n\n'
                        response += html_template.format(file_content=file_content)
                        cl.sendall(response.encode())
                    except Exception as e:
                        print("Error handling request:", e)
                    finally:
                        cl.close()
                        led.off()

                elif ready_socket == dns:
                    data, addr = dns.recvfrom(512)
                    handle_dns_request(data, addr, dns, ip_address)

# Start the server
start_server()
