# Import necessary modules
# - Flask: A lightweight web framework for building web applications in Python.
# - render_template: A function used to render HTML files stored in the 'templates' folder.
# - socket: A library to get the hostname and IP address of the system.
from flask import Flask, render_template
import socket

# Create an instance of the Flask class. 
# This creates a web application object. 
# '__name__' helps Flask know where to look for resources like templates.
app = Flask(__name__)

# Define a route (URL) for the web application.
# When someone visits the root URL ("/"), the 'index' function will be called.
@app.route("/")
def index():
    try:
        # Get the hostname (name of the server/machine) using the socket library.
        host_name = socket.gethostname()
        
        # Get the IP address of the machine using the hostname.
        host_ip = socket.gethostbyname(host_name)
        
        # Render the 'index.html' file from the 'templates' folder, 
        # passing the hostname and IP address to the template for display.
        return render_template('index.html', hostname=host_name, ip=host_ip)
    except:
        # If there is an error (e.g., can't fetch hostname or IP),
        # render the 'error.html' file from the 'templates' folder.
        return render_template('error.html')

# This block ensures that the Flask app runs only when this script is executed directly.
# The application will run on all IP addresses of the host (0.0.0.0) and listen on port 8080.
# This is important for when the app runs in a container (like in AKS), where it needs 
# to be accessible from outside the container.
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
