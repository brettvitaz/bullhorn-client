from flask import Flask, request, jsonify

from server.bullhorn import Bullhorn, get_auth_code

app = Flask(__name__)

bh = None


@app.route('/oauth/authenticate')
def authenticate():
    if 'client_id' in request.args and 'username' in request.args and 'password' in request.args:
        try:
            return jsonify(code=get_auth_code(**request.args))
        except:
            pass

    return jsonify(error='invalid request'), 400


@app.route('/login')
def login():
    global bh
    bh = Bullhorn(request.args['client_id'],
                  request.args['client_secret'],
                  request.args['username'],
                  request.args['password'])
    return jsonify(message='logged in')


@app.route('/rest-services/<path:path>')
def proxy(path):
    if bh is not None:
        response, status_code = bh.proxy(path, request.args)
        return jsonify(response), status_code
    return jsonify(error='login first'), 401


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
