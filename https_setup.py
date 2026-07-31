# Generate self signed cert
#openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt -days 365 -nodes

#streamlit run app.py  --server.port 9000 --server.sslCertFile=/path/server.crt --server.sslKeyFile=/path/server.key

#OR

from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello HTTPS"

app.run(
    host="0.0.0.0",
    port=9000,
    ssl_context=("server.crt", "server.key")
)
