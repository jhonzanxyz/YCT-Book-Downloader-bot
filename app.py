import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <center>
        <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQQUXl0VxzLOL5frACn_1QdkwWZQu0vY73vf9IpIRJfW-Nh9JScWR6Lxts&s=10" style="border-radius: 2px;"/>/>
    </center>
    <style>
        body {
            background: antiquewhite;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100vh;
            margin: 0;
        }
        footer {
            text-align: center;
            padding: 10px;
            background: antiquewhite;
            font-size: 1.2em;
        }
    </style>
    <footer>
        Made with 💕 by devgagan.in
    </footer>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
